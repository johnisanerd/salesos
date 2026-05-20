from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError, TimeoutError

from salesos_shared.retry import retry_async


class RedisStateStore:
    def __init__(
        self,
        redis: Redis,
        *,
        operation_timeout_seconds: float = 5.0,
        retry_attempts: int = 2,
    ) -> None:
        self.redis = redis
        self.operation_timeout_seconds = operation_timeout_seconds
        self.retry_attempts = retry_attempts

    async def ping(self) -> bool:
        return bool(
            await self._execute(lambda: self.redis.ping(), operation_name="redis_ping"),
        )

    async def set_json(self, key: str, value: Mapping[str, Any], *, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(dict(value), default=str)
        await self._execute(lambda: self.redis.set(key, payload, ex=ttl_seconds), operation_name="redis_set_json")

    async def get_json(self, key: str) -> dict[str, Any] | None:
        payload = await self._execute(lambda: self.redis.get(key), operation_name="redis_get_json")
        if payload is None:
            return None
        return json.loads(payload)

    async def push_json(
        self,
        key: str,
        value: Mapping[str, Any],
        *,
        max_items: int = 100,
        ttl_seconds: int | None = None,
    ) -> None:
        payload = json.dumps(dict(value), default=str)
        await self._execute(lambda: self.redis.lpush(key, payload), operation_name="redis_lpush_json")
        await self._execute(lambda: self.redis.ltrim(key, 0, max_items - 1), operation_name="redis_ltrim_json")
        if ttl_seconds is not None:
            await self._execute(lambda: self.redis.expire(key, ttl_seconds), operation_name="redis_expire")

    async def get_list(self, key: str, *, limit: int = 10) -> list[dict[str, Any]]:
        values = await self._execute(lambda: self.redis.lrange(key, 0, max(0, limit - 1)), operation_name="redis_lrange")
        return [json.loads(item) for item in values]

    async def set_text(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        await self._execute(lambda: self.redis.set(key, value, ex=ttl_seconds), operation_name="redis_set_text")

    async def get_text(self, key: str) -> str | None:
        return await self._execute(lambda: self.redis.get(key), operation_name="redis_get_text")

    async def close(self) -> None:
        await self.redis.aclose()

    async def _execute(self, operation, *, operation_name: str):
        return await retry_async(
            operation,
            attempts=self.retry_attempts,
            timeout_seconds=self.operation_timeout_seconds,
            retry_exceptions=(ConnectionError, TimeoutError),
            retry_context={"service": "redis", "retry_operation": operation_name},
        )
