from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_free_user_allowed_within_limit():
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=3)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=3600)
        mock_redis.return_value = mock_client

        from middleware.rate_limit import RateLimiter

        limiter = RateLimiter("redis://localhost")
        allowed, remaining = await limiter.is_allowed(12345, is_premium=False)
        assert allowed is True
        assert remaining == 2


@pytest.mark.asyncio
async def test_free_user_blocked_over_limit():
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=6)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=3600)
        mock_redis.return_value = mock_client

        from middleware.rate_limit import RateLimiter

        limiter = RateLimiter("redis://localhost")
        allowed, remaining = await limiter.is_allowed(12345, is_premium=False)
        assert allowed is False


@pytest.mark.asyncio
async def test_premium_user_always_allowed():
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=999)
        mock_client.expire = AsyncMock()
        mock_client.ttl = AsyncMock(return_value=3600)
        mock_redis.return_value = mock_client

        from middleware.rate_limit import RateLimiter

        limiter = RateLimiter("redis://localhost")
        allowed, remaining = await limiter.is_allowed(99999, is_premium=True)
        assert allowed is True
