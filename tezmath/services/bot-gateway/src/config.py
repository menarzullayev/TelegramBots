from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram (majburiy)
    bot_token: str
    webhook_secret: str = "dev_secret"
    webhook_url: str = ""

    # AI (majburiy)
    anthropic_api_key: str

    # Database
    sqlite_path: str = "tezmath.db"

    # Ixtiyoriy (hozircha ishlatilmaydi)
    database_url: str = ""
    redis_url: str = ""
    rabbitmq_url: str = ""
    internal_api_key: str = "changeme"

    # App
    environment: str = "development"
    log_level: str = "INFO"
    admin_ids: str = ""
    free_daily_limit: int = 5
    sentry_dsn: str = ""

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.split(",") if x.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
