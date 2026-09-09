import logging
from collections import defaultdict
from datetime import date

import redis.asyncio as redis

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# In-memory store: {(user_id, date_str): count}
_counters: dict[tuple, int] = defaultdict(int)


class RateLimiter:
    def __init__(self, redis_url: str = ""):
        self.redis_url = redis_url
        self.redis = None
        if redis_url:
            self.redis = redis.from_url(redis_url, decode_responses=True)

    async def is_allowed(self, user_id: int, is_premium: bool) -> tuple[bool, int]:
        if is_premium:
            return True, 999999

        limit = settings.free_daily_limit
        today = str(date.today())

        if self.redis:
            try:
                key = f"rate_limit:{user_id}:{today}"
                count = await self.redis.incr(key)
                if count == 1:
                    await self.redis.expire(key, 86400)  # 24 hours

                remaining = max(0, limit - count)
                return count <= limit, remaining
            except Exception as e:
                logger.error(f"Redis error: {e}")
                # Fallback to in-memory if Redis fails

        key = (user_id, today)
        _counters[key] += 1
        count = _counters[key]
        remaining = max(0, limit - count)
        return count <= limit, remaining

    async def get_remaining(self, user_id: int) -> int:
        today = str(date.today())
        limit = settings.free_daily_limit

        if self.redis:
            try:
                key = f"rate_limit:{user_id}:{today}"
                val = await self.redis.get(key)
                count = int(val) if val else 0
                return max(0, limit - count)
            except Exception:
                pass

        count = _counters.get((user_id, today), 0)
        return max(0, limit - count)

    async def reset(self, user_id: int):
        today = str(date.today())
        if self.redis:
            try:
                key = f"rate_limit:{user_id}:{today}"
                await self.redis.delete(key)
            except Exception:
                pass

        _counters.pop((user_id, today), None)
