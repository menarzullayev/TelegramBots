import logging

from auth import router as auth_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analytics, broadcast, payments, users

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="TezMath Admin Panel", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(broadcast.router, prefix="/api/v1/broadcast", tags=["broadcast"])


@app.get("/health")
async def health():
    return {"status": "ok"}
