import json
import logging
import uuid
from functools import lru_cache

import aio_pika
from auth import verify_token
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings

router = APIRouter(dependencies=[Depends(verify_token)])
logger = logging.getLogger(__name__)


class BroadcastSettings(BaseSettings):
    rabbitmq_url: str

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> BroadcastSettings:
    return BroadcastSettings()


class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"  # all | premium | free


@router.post("")
async def send_broadcast(req: BroadcastRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    settings = get_settings()
    job_id = str(uuid.uuid4())

    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue("notification.broadcast", durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps({"job_id": job_id, "message": req.message, "target": req.target}).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="notification.broadcast",
            )
    except Exception as e:
        logger.error(f"Broadcast queue error: {e}")
        raise HTTPException(status_code=500, detail="Queue error")

    return {"job_id": job_id, "status": "queued"}
