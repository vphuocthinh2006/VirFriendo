"""Optional async Redis client (REDIS_URL). Safe no-op when unset, package missing, or connection fails."""

from __future__ import annotations

from typing import Any

from loguru import logger

from services.core.config import settings

_client: Any = None  # Redis | None; False = disabled


async def get_redis():
    """Return shared Redis client or None if disabled / unavailable."""
    global _client
    if _client is False:
        return None
    if _client is not None:
        return _client
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis package not installed; install `redis` for Quickstart personality cache")
        _client = False
        return None
    url = (settings.REDIS_URL or "").strip()
    if not url:
        _client = False
        return None
    try:
        _client = aioredis.from_url(url, decode_responses=True)
        return _client
    except Exception as e:
        logger.warning("Redis unavailable: {}", e)
        _client = False
        return None
