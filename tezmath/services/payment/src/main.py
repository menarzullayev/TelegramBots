import logging

from fastapi import FastAPI
from routers import click, orders, payme, webhooks

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="TezMath Payment Service", version="1.0.0")

app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(payme.router, prefix="/api/v1/payme", tags=["payme"])
app.include_router(click.router, prefix="/api/v1/click", tags=["click"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "ok"}
