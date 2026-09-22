from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DECISION-01: single-node — sqlite + polling + in-process lock."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    bot_username: str = "qorashahar_mafia_bot"
    owner_id: int | None = None
    database_url: str = "sqlite+aiosqlite:///./data/tezmafia.db"

    @field_validator("database_url")
    @classmethod
    def sqlite_only(cls, value: str) -> str:
        if not value.startswith("sqlite"):
            raise ValueError("DECISION-01: database_url must be sqlite (single-node contract)")
        return value
    min_players: int = 5
    max_players: int = 23
    discussion_seconds: int = 90
    night_action_seconds: int = 45
    voting_seconds: int = 45
    lynch_seconds: int = 25
    lobby_seconds: int = 180
    extend_seconds: int = 90
    max_extends: int = 3
    tie_seconds: int = 20
    mafia_resolve: str = "majority"
    reveal_on_death: bool = True
    first_phase: str = "night_kill"
    mute_dead: bool = True
    mute_night: bool = True
    log_level: str = "INFO"
