from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str = ""
    gemini_api_key: str = ""
    rabbitmq_url: str
    database_url: str
    redis_url: str
    s3_endpoint: str = "http://minio:9000"
    s3_bucket: str = "tezmath"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    renderer_url: str = "http://renderer:8001"
    primary_model: str = "anthropic"
    max_tokens: int = 4096
    sentry_dsn: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
