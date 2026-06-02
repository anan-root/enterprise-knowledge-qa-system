import asyncio
import os

import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_redis: aioredis.Redis | None = None
_lock = asyncio.Lock()


async def get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is not None:
        return _redis

    async with _lock:
        if _redis is not None:
            return _redis

        try:
            _redis = aioredis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD") or None,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            await _redis.ping()
            print("Redis connected")
        except Exception as e:
            print(f"Redis unavailable, running without cache: {e}")
            _redis = None
        return _redis
