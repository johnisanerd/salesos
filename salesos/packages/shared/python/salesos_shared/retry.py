from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from salesos_shared.logging import get_logger, log_extra


T = TypeVar("T")
RetryHook = Callable[[int, BaseException], object]
logger = get_logger(__name__)


class RetryError(RuntimeError):
    pass


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    timeout_seconds: float | None = None,
    backoff_seconds: float = 0.25,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: RetryHook | None = None,
    retry_context: dict[str, object] | None = None,
) -> T:
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            task = operation()
            if timeout_seconds is not None:
                return await asyncio.wait_for(task, timeout=timeout_seconds)
            return await task
        except BaseException as exc:
            is_retryable = isinstance(exc, retry_exceptions)
            if isinstance(exc, TimeoutError):
                # Local operation timeouts from asyncio.wait_for should participate
                # in the same retry flow as provider-specific timeout exceptions.
                is_retryable = True
            if not is_retryable:
                raise
            last_error = exc
            if attempt == attempts:
                break
            retry_delay = backoff_seconds * attempt
            logger.warning(
                "Retrying async operation after failure",
                extra=log_extra(
                    retry_attempt=attempt,
                    retry_max_attempts=attempts,
                    retry_delay_seconds=retry_delay,
                    retry_failure_reason=str(exc) or exc.__class__.__name__,
                    retry_exception_type=exc.__class__.__name__,
                    retry_timeout_seconds=timeout_seconds,
                    **(retry_context or {}),
                ),
            )
            if on_retry is not None:
                retry_result = on_retry(attempt, exc)
                if asyncio.iscoroutine(retry_result):
                    await retry_result
            await asyncio.sleep(retry_delay)

    raise RetryError(str(last_error)) from last_error
