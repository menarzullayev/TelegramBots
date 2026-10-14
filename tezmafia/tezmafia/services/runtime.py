"""Process-level plumbing: per-chat locks, flood-limit retries, single instance, owner alerts."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType

log = logging.getLogger("tezmafia")


class ChatLocks:
    """One asyncio.Lock per chat, so a slow table never blocks another one."""

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def __call__(self, chat_id: int) -> asyncio.Lock:
        return self._locks[chat_id]

    @asynccontextmanager
    async def hold(self, chat_id: int) -> AsyncIterator[None]:
        async with self._locks[chat_id]:
            yield


class RetryAfterMiddleware(BaseRequestMiddleware):
    """Wait out Telegram flood limits (429) instead of failing the call.

    Long waits are not worth blocking a game for: anything above max_wait is raised as before.
    """

    def __init__(self, attempts: int = 3, max_wait: float = 30.0) -> None:
        self.attempts = attempts
        self.max_wait = max_wait

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        for attempt in range(self.attempts):
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as exc:
                wait = float(exc.retry_after)
                if wait > self.max_wait or attempt == self.attempts - 1:
                    raise
                log.warning("flood limit on %s, retry in %.0fs", type(method).__name__, wait)
                await asyncio.sleep(wait + 0.5)
        raise RuntimeError("unreachable")  # pragma: no cover


class InstanceLock:
    """Exclusive lock file: two pollers with one token would steal each other's updates."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Any = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()}\n")
        fh.flush()
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


class Alerter:
    """Short DMs to the bot owner; the same alert key is sent at most once per cooldown."""

    def __init__(self, bot: Bot, owner_id: int | None, cooldown: float = 600.0) -> None:
        self.bot = bot
        self.owner_id = owner_id
        self.cooldown = cooldown
        self._last: dict[str, float] = {}
        self._muted: dict[str, int] = defaultdict(int)

    def _due(self, key: str) -> bool:
        now = time.monotonic()
        if now - self._last.get(key, -1e9) < self.cooldown:
            self._muted[key] += 1
            return False
        self._last[key] = now
        return True

    async def send(self, key: str, text: str) -> bool:
        if not self.owner_id or not self._due(key):
            return False
        skipped = self._muted.pop(key, 0)
        if skipped:
            text += f"\n(+{skipped} shunga o'xshash)"
        try:
            await self.bot.send_message(self.owner_id, text[:4000], parse_mode=None)
            return True
        except (TelegramAPIError, OSError):
            log.warning("owner alert failed key=%s", key, exc_info=True)
            return False
