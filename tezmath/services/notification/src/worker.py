import asyncio
import json
import logging
from functools import lru_cache

import aio_pika
import asyncpg
import httpx
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BROADCAST_QUEUE = "notification.broadcast"


class Settings(BaseSettings):
    rabbitmq_url: str
    database_url: str
    bot_token: str

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
_pool: asyncpg.Pool | None = None

TELEGRAM_API = f"https://api.telegram.org/bot{settings.bot_token}"
BATCH_SIZE = 25
DELAY_BETWEEN_BATCHES = 1.0  # seconds


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=5)
    return _pool


async def send_message(telegram_id: int, text: str) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": telegram_id, "text": text, "parse_mode": "Markdown"},
            )
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Send failed for {telegram_id}: {e}")
            return False


async def process_broadcast(message: aio_pika.IncomingMessage):
    async with message.process():
        payload = json.loads(message.body)
        text = payload["message"]
        job_id = payload["job_id"]

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT telegram_id FROM users WHERE is_banned = FALSE ORDER BY id")

        user_ids = [r["telegram_id"] for r in rows]
        logger.info(f"Broadcast job={job_id}: sending to {len(user_ids)} users")

        sent = 0
        failed = 0
        for i in range(0, len(user_ids), BATCH_SIZE):
            batch = user_ids[i : i + BATCH_SIZE]
            results = await asyncio.gather(*[send_message(uid, text) for uid in batch])
            sent += sum(results)
            failed += sum(1 for r in results if not r)
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)

        logger.info(f"Broadcast job={job_id} done: sent={sent} failed={failed}")


async def main():
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(BROADCAST_QUEUE, durable=True)
    await queue.consume(process_broadcast)

    logger.info("Notification worker started")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
