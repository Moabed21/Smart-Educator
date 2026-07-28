import redis.asyncio as redis
from helpers.config import get_settings

settings = get_settings()

# Single shared connection pool for the whole app lifetime.
# Created once at import time, reused by every request (no reconnect per call).
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
)


async def get_cached(key: str) -> str | None:
    """
    Fetch a cached value by key.
    Returns the string value if found, or None if the key doesn't exist (cache miss).
    """
    return await redis_client.get(key)


async def set_cached(key: str, value: str, ttl_seconds: int) -> None:
    """
    Store a value under a key, with an expiration time (TTL).
    After ttl_seconds, Redis automatically deletes the key on its own.
    """
    await redis_client.set(key, value, ex=ttl_seconds)