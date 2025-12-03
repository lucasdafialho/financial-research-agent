import hashlib
import json
from typing import Any, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

from src.config.logging import LoggerMixin
from src.config.settings import Settings

T = TypeVar("T", bound=BaseModel)


class CacheService(LoggerMixin):
    """Redis cache service for caching API responses and computed data."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: redis.Redis | None = None
        self._default_ttl = settings.redis_cache_ttl

    async def connect(self) -> None:
        """Connect to Redis."""
        self._client = redis.from_url(
            self._settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self.logger.info("cache_connected")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self.logger.info("cache_closed")

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Cache not connected. Call connect() first.")
        return self._client

    @staticmethod
    def generate_key(*parts: str) -> str:
        """Generate a cache key from parts."""
        key_string = ":".join(str(p) for p in parts)
        return f"fra:{hashlib.md5(key_string.encode()).hexdigest()}"

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        try:
            return await self.client.get(key)
        except Exception as e:
            self.logger.warning("cache_get_error", key=key, error=str(e))
            return None

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Get a JSON value from cache."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def get_model(self, key: str, model_class: type[T]) -> T | None:
        """Get a Pydantic model from cache."""
        data = await self.get_json(key)
        if data:
            try:
                return model_class.model_validate(data)
            except Exception:
                return None
        return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in cache."""
        try:
            await self.client.setex(key, ttl or self._default_ttl, value)
            return True
        except Exception as e:
            self.logger.warning("cache_set_error", key=key, error=str(e))
            return False

    async def set_json(
        self,
        key: str,
        value: dict[str, Any] | list[Any],
        ttl: int | None = None,
    ) -> bool:
        """Set a JSON value in cache."""
        return await self.set(key, json.dumps(value, default=str), ttl)

    async def set_model(
        self,
        key: str,
        model: BaseModel,
        ttl: int | None = None,
    ) -> bool:
        """Set a Pydantic model in cache."""
        return await self.set_json(key, model.model_dump(mode="json"), ttl)

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            self.logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        try:
            keys = []
            async for key in self.client.scan_iter(f"fra:{pattern}*"):
                keys.append(key)
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            self.logger.warning("cache_delete_pattern_error", pattern=pattern, error=str(e))
            return 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            self.logger.warning("cache_increment_error", key=key, error=str(e))
            return 0

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int]:
        """Check if rate limit is exceeded."""
        key = f"fra:ratelimit:{identifier}"
        try:
            current = await self.client.get(key)
            if current is None:
                await self.client.setex(key, window, 1)
                return True, limit - 1
            current_int = int(current)
            if current_int >= limit:
                return False, 0
            await self.client.incr(key)
            return True, limit - current_int - 1
        except Exception as e:
            self.logger.warning("rate_limit_check_error", error=str(e))
            return True, limit

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            await self.client.ping()
            return True
        except Exception as e:
            self.logger.error("cache_health_check_failed", error=str(e))
            return False


_cache_service: CacheService | None = None


async def get_cache_service(settings: Settings | None = None) -> CacheService:
    """Get or create the cache service singleton."""
    global _cache_service
    if _cache_service is None:
        if settings is None:
            from src.config.settings import get_settings

            settings = get_settings()
        _cache_service = CacheService(settings)
        await _cache_service.connect()
    return _cache_service
