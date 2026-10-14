"""Own MAU/DAU counters: Telegram does not publish how it counts a bot's monthly users."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

log = logging.getLogger("tezmafia")


def channel_of(update: Update) -> tuple[int, str] | None:
    """(user_id, "dm" | "group") for updates a person caused; None for service updates."""
    if update.message and update.message.from_user and not update.message.from_user.is_bot:
        kind = "dm" if update.message.chat.type == "private" else "group"
        return update.message.from_user.id, kind
    if update.callback_query and update.callback_query.from_user:
        msg = update.callback_query.message
        kind = "dm" if msg is not None and msg.chat.type == "private" else "group"
        return update.callback_query.from_user.id, kind
    if update.pre_checkout_query:
        return update.pre_checkout_query.from_user.id, "dm"
    return None


class ActivityMiddleware(BaseMiddleware):
    """Records (day, user, channel) once per day; the in-memory set keeps it to one write per triple."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self._seen: set[tuple[str, int, str]] = set()
        self._day = ""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            hit = channel_of(event)
            if hit:
                day = time.strftime("%Y-%m-%d")
                if day != self._day:
                    self._day, self._seen = day, set()
                key = (day, *hit)
                if key not in self._seen:
                    self._seen.add(key)
                    try:
                        await self.store.touch_activity(day, hit[0], hit[1])
                    except Exception:
                        log.warning("activity write failed", exc_info=True)
        return await handler(event, data)
