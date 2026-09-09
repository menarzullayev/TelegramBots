"""Click payment system handler."""

import hashlib
import logging

import asyncpg
from fastapi import APIRouter, Form

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


def _verify_sign(
    click_trans_id,
    service_id,
    click_paydoc_id,
    merchant_trans_id,
    amount,
    action,
    sign_time,
    sign_string,
) -> bool:
    key = f"{click_trans_id}{service_id}{settings.click_secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
    expected = hashlib.md5(key.encode()).hexdigest()
    return expected == sign_string


@router.post("/prepare")
async def click_prepare(
    click_trans_id: int = Form(...),
    service_id: int = Form(...),
    click_paydoc_id: int = Form(...),
    merchant_trans_id: str = Form(...),
    amount: float = Form(...),
    action: int = Form(...),
    sign_time: str = Form(...),
    sign_string: str = Form(...),
):
    if not _verify_sign(
        click_trans_id,
        service_id,
        click_paydoc_id,
        merchant_trans_id,
        amount,
        action,
        sign_time,
        sign_string,
    ):
        return {"error": -1, "error_note": "Invalid sign"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM transactions WHERE id = $1", merchant_trans_id)
    if not row:
        return {"error": -5, "error_note": "Order not found"}

    return {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": click_trans_id,
        "error": 0,
        "error_note": "Success",
    }


@router.post("/complete")
async def click_complete(
    click_trans_id: int = Form(...),
    service_id: int = Form(...),
    click_paydoc_id: int = Form(...),
    merchant_trans_id: str = Form(...),
    merchant_prepare_id: int = Form(...),
    amount: float = Form(...),
    action: int = Form(...),
    error: int = Form(...),
    error_note: str = Form(...),
    sign_time: str = Form(...),
    sign_string: str = Form(...),
):
    if not _verify_sign(
        click_trans_id,
        service_id,
        click_paydoc_id,
        merchant_trans_id,
        amount,
        action,
        sign_time,
        sign_string,
    ):
        return {"error": -1, "error_note": "Invalid sign"}

    if error != 0:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE transactions SET status = 'cancelled' WHERE id = $1", merchant_trans_id)
        return {"error": 0, "error_note": "Cancelled"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE transactions SET status = 'completed' WHERE id = $1 RETURNING user_id",
            merchant_trans_id,
        )
        if row:
            await conn.execute(
                "UPDATE users SET is_premium = TRUE, subscription_end = GREATEST(NOW(), subscription_end) + '1 month'::interval WHERE id = $1",
                row["user_id"],
            )

    logger.info(f"Click payment completed: {merchant_trans_id}")
    return {"error": 0, "error_note": "Success", "merchant_trans_id": merchant_trans_id}
