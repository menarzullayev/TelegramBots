from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    payme_merchant_id: str = ""
    payme_secret_key: str = ""
    click_merchant_id: str = ""
    click_service_id: str = ""
    click_secret_key: str = ""
    internal_api_key: str
    bot_gateway_url: str = "http://bot-gateway:8000"
    sentry_dsn: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
