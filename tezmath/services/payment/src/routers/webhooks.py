"""Generic webhook placeholder for future integrations."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def webhook_status():
    return {"status": "ok"}
