import logging
import uuid

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from config import get_settings

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

PAYME_BASE = "https://checkout.paycom.uz"
CLICK_BASE = "https://my.click.uz/services/pay"


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=2, max_size=5)
    return _pool


def verify_internal_key(x_internal_key: str = Header(...)):
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


class OrderRequest(BaseModel):
    user_id: int
    method: str  # payme | click
    amount: int  # UZS
    period: str  # monthly | yearly


class OrderResponse(BaseModel):
    order_id: str
    payment_url: str
    amount: int


@router.post("", response_model=OrderResponse, dependencies=[Depends(verify_internal_key)])
async def create_order(req: OrderRequest):
    order_id = str(uuid.uuid4())
    amount_tiyin = req.amount * 100  # Payme uses tiyin (1/100 UZS)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transactions (id, user_id, amount, method, status, period, created_at)
            VALUES ($1, $2, $3, $4, 'pending', $5, NOW())
            """,
            order_id,
            req.user_id,
            req.amount,
            req.method,
            req.period,
        )

    if req.method == "payme":
        encoded = _payme_encode(order_id, amount_tiyin)
        payment_url = f"{PAYME_BASE}/{encoded}"
    elif req.method == "click":
        payment_url = (
            f"{CLICK_BASE}?service_id={settings.click_service_id}"
            f"&merchant_id={settings.click_merchant_id}"
            f"&amount={req.amount}&transaction_param={order_id}"
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown method")

    logger.info(f"Order created: {order_id} user={req.user_id} method={req.method}")
    return OrderResponse(order_id=order_id, payment_url=payment_url, amount=req.amount)


def _payme_encode(order_id: str, amount_tiyin: int) -> str:
    import base64

    payload = f"m={settings.payme_merchant_id};ac.order_id={order_id};a={amount_tiyin}"
    return base64.b64encode(payload.encode()).decode()
