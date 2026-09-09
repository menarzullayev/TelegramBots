import hashlib
import time
from functools import lru_cache

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pydantic_settings import BaseSettings

router = APIRouter()
bearer = HTTPBearer()


class Settings(BaseSettings):
    admin_secret: str = "changeme"
    jwt_secret: str = "changeme"
    admin_password_hash: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(username: str) -> str:
    settings = get_settings()
    payload = {"sub": username, "iat": int(time.time()), "exp": int(time.time()) + 86400}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    settings = get_settings()
    if req.username != "admin" or _hash_password(req.password) != settings.admin_password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_token(req.username))
