"""Payme merchant API handler (JSON-RPC 2.0)."""

import base64
import logging

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=5)
    return _pool


def _verify_auth(request: Request) -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        _, password = decoded.split(":", 1)
        return password == settings.payme_secret_key
    except Exception:
        return False


@router.post("")
async def payme_handler(request: Request):
    if not _verify_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    rpc_id = body.get("id")

    handlers = {
        "CheckPerformTransaction": _check_perform,
        "CreateTransaction": _create_transaction,
        "PerformTransaction": _perform_transaction,
        "CancelTransaction": _cancel_transaction,
        "CheckTransaction": _check_transaction,
        "GetStatement": _get_statement,
    }

    handler = handlers.get(method)
    if not handler:
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": "Method not found"},
        }

    try:
        result = await handler(params)
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}
    except Exception as e:
        logger.error(f"Payme handler error: {e}")
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -31008, "message": str(e)}}


async def _check_perform(params: dict) -> dict:
    order_id = params.get("account", {}).get("order_id")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT amount FROM transactions WHERE id = $1", order_id)
    if not row:
        return {"error": {"code": -31050, "message": "Order not found"}}
    return {"allow": True}


async def _create_transaction(params: dict) -> dict:
    import time

    order_id = params["account"]["order_id"]
    payme_id = params["id"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE transactions SET payme_id = $1, status = 'processing' WHERE id = $2",
            payme_id,
            order_id,
        )
    return {"create_time": int(time.time() * 1000), "transaction": payme_id, "state": 1}


async def _perform_transaction(params: dict) -> dict:
    import time

    payme_id = params["id"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE transactions SET status = 'completed', perform_time = NOW() WHERE payme_id = $1 RETURNING user_id, amount, period",
            payme_id,
        )
        if row:
            await conn.execute(
                """UPDATE users SET is_premium = TRUE,
                   subscription_end = GREATEST(NOW(), subscription_end) + ('1 month')::interval
                   WHERE id = $1""",
                row["user_id"],
            )
    return {"perform_time": int(time.time() * 1000), "transaction": payme_id, "state": 2}


async def _cancel_transaction(params: dict) -> dict:
    import time

    payme_id = params["id"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE transactions SET status = 'cancelled', cancel_time = NOW() WHERE payme_id = $1",
            payme_id,
        )
    return {"cancel_time": int(time.time() * 1000), "transaction": payme_id, "state": -1}


async def _check_transaction(params: dict) -> dict:
    payme_id = params["id"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM transactions WHERE payme_id = $1", payme_id)
    if not row:
        return {"error": {"code": -31003, "message": "Transaction not found"}}
    state = {"completed": 2, "cancelled": -1, "processing": 1}.get(row["status"], 1)
    return {
        "create_time": int(row["created_at"].timestamp() * 1000),
        "transaction": payme_id,
        "state": state,
    }


async def _get_statement(params: dict) -> dict:
    return {"transactions": []}
