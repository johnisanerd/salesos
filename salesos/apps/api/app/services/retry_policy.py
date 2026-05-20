from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import httpx

from app.core.settings import settings
from app.models.enums import FailureCategory
from salesos_shared.logging import get_logger, log_extra
from salesos_shared.retry import RetryError, retry_async


logger = get_logger(__name__)


@dataclass(slots=True)
class RetryExecutionResult:
    value: object | None
    retry_count: int
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    retryable: bool = False


class CentralRetryPolicy:
    def __init__(self) -> None:
        self.attempts = max(settings.pipeline_retry_attempts, 1)
        self.backoff_seconds = max(settings.pipeline_retry_backoff_seconds, 0.0)

    async def run(
        self,
        operation,
        *,
        workflow_name: str,
        stage_name: str,
        correlation_id: str,
        lead_id: uuid.UUID | None = None,
    ) -> RetryExecutionResult:
        retry_count = 0

        def on_retry(attempt: int, exc: BaseException) -> None:
            nonlocal retry_count
            retry_count = attempt
            logger.warning(
                "Retry policy triggered",
                extra=log_extra(
                    workflow_name=workflow_name,
                    stage_name=stage_name,
                    correlation_id=correlation_id,
                    lead_id=str(lead_id) if lead_id else None,
                    retry_attempt=attempt,
                    failure_category=self.classify_failure(exc).value,
                ),
            )

        try:
            value = await retry_async(
                operation,
                attempts=self.attempts,
                backoff_seconds=self.backoff_seconds,
                on_retry=on_retry,
                retry_context={
                    "workflow_name": workflow_name,
                    "stage_name": stage_name,
                    "correlation_id": correlation_id,
                    "lead_id": str(lead_id) if lead_id else None,
                },
                retry_exceptions=(asyncio.TimeoutError, TimeoutError, ConnectionError, httpx.HTTPError, RuntimeError),
            )
            return RetryExecutionResult(value=value, retry_count=retry_count)
        except Exception as exc:
            category = self.classify_failure(exc.__cause__ or exc)
            return RetryExecutionResult(
                value=None,
                retry_count=retry_count if retry_count else max(self.attempts - 1, 0),
                failure_category=category,
                error_message=str(exc) or exc.__class__.__name__,
                retryable=self.is_retryable(category),
            )

    @staticmethod
    def classify_failure(exc: BaseException) -> FailureCategory:
        if isinstance(exc, (ValueError, TypeError)):
            return FailureCategory.validation
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return FailureCategory.timeout
        if isinstance(exc, (ConnectionError, httpx.HTTPError, RetryError)):
            return FailureCategory.dependency
        return FailureCategory.unknown

    @staticmethod
    def is_retryable(category: FailureCategory) -> bool:
        return category in {FailureCategory.timeout, FailureCategory.dependency, FailureCategory.delivery, FailureCategory.ai}
