import json
import logging
import uuid

import aio_pika

from config import get_settings
from services.queue_producer import _get_channel

settings = get_settings()
logger = logging.getLogger(__name__)

BROADCAST_QUEUE = "notification.broadcast"


async def publish_broadcast(message: str) -> str:
    channel = await _get_channel()
    await channel.declare_queue(BROADCAST_QUEUE, durable=True)

    job_id = str(uuid.uuid4())
    payload = {"job_id": job_id, "message": message}

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=BROADCAST_QUEUE,
    )

    logger.info(f"Broadcast job queued: job_id={job_id}")
    return job_id
