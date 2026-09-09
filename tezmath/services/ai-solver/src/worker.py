import asyncio
import base64
import json
import logging

import aio_pika
import asyncpg
from renderer_client import render_latex
from solvers.fallback import FallbackSolver

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

SOLVER_QUEUE = "solver.tasks"
solver = FallbackSolver()
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=10)
    return _pool


async def save_solution(
    user_id: int, input_type: str, input_text: str, solution_text: str, model: str, tokens: int
) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO solutions (user_id, input_type, input_text, solution_text, model_used, tokens_used, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id
            """,
            user_id,
            input_type,
            input_text,
            solution_text,
            model,
            tokens,
        )
        return row["id"]


async def process_task(message: aio_pika.IncomingMessage):
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body)
            user_id = payload["user_id"]
            lang = payload.get("lang", "uz")
            input_type = payload["input_type"]
            content = payload.get("content", "")
            image_data: bytes | None = None

            if payload.get("image_b64"):
                image_data = base64.b64decode(payload["image_b64"])

            logger.info(f"Processing task for user_id={user_id} type={input_type}")

            result = await solver.solve(content, image_data, lang)

            render_url: str | None = None
            if result.latex_source:
                render_url = await render_latex(result.latex_source)

            solution_id = await save_solution(
                user_id=user_id,
                input_type=input_type,
                input_text=content[:500],
                solution_text=result.solution_text,
                model=result.model_used,
                tokens=result.tokens_used,
            )

            response = {
                "solution_id": solution_id,
                "solution_text": result.solution_text,
                "render_url": render_url,
            }

            await message.channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(response).encode(),
                    correlation_id=message.correlation_id,
                ),
                routing_key=message.reply_to,
            )

            logger.info(f"Task done: solution_id={solution_id} model={result.model_used} tokens={result.tokens_used}")

        except Exception as e:
            logger.error(f"Task processing error: {e}", exc_info=True)
            error_response = {
                "error": str(e),
                "solution_text": "❌ Yechimda xatolik yuz berdi.",
                "solution_id": 0,
            }
            try:
                await message.channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(error_response).encode(),
                        correlation_id=message.correlation_id,
                    ),
                    routing_key=message.reply_to,
                )
            except Exception:
                pass


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("AI Solver worker starting...")

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=4)

    queue = await channel.declare_queue(SOLVER_QUEUE, durable=True)
    await queue.consume(process_task)

    logger.info(f"Listening on queue '{SOLVER_QUEUE}'")
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
