import logging

import httpx

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

PAYMENT_SERVICE_URL = "http://payment:8002"


async def create_payment_order(
    *,
    user_id: int,
    method: str,
    amount: int,
    period: str,
) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{PAYMENT_SERVICE_URL}/api/v1/orders",
                json={"user_id": user_id, "method": method, "amount": amount, "period": period},
                headers={"X-Internal-Key": settings.internal_api_key},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Payment service error: {e}")
        return None
