from redis.asyncio import Redis

from bot.config import settings
from salesos_shared.redis import RedisStateStore


redis_client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
redis_state = RedisStateStore(
    redis_client,
    operation_timeout_seconds=settings.redis_operation_timeout_seconds,
    retry_attempts=settings.redis_retry_attempts,
)
