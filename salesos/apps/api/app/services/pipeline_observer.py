from __future__ import annotations

import time
import traceback
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis import redis_state
from app.models.enums import FailureCategory, PipelineStage, WorkflowStatus
from app.models.workflow_log import WorkflowLog
from app.repositories.workflow_repository import WorkflowLogRepository
from app.schemas.pipeline import PipelineEvent
from app.services.dead_letter_service import DeadLetterService
from app.services.retry_policy import CentralRetryPolicy
from salesos_shared.logging import get_logger, log_extra, request_id_context


logger = get_logger(__name__)


class PipelineObserver:
    def __init__(
        self,
        session: AsyncSession,
        *,
        workflow_name: str,
        workflow_run_id: uuid.UUID,
        campaign_id: uuid.UUID | None,
    ) -> None:
        self.session = session
        self.workflow_name = workflow_name
        self.workflow_run_id = workflow_run_id
        self.campaign_id = campaign_id
        self.workflow_logs = WorkflowLogRepository(session)
        self.dead_letters = DeadLetterService(session)
        self.retry_policy = CentralRetryPolicy()
        self.failures: list[dict[str, Any]] = []
        self.correlation_id = request_id_context.get() or str(workflow_run_id)

    @asynccontextmanager
    async def stage(
        self,
        workflow_stage: str,
        *,
        lead_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        start = time.perf_counter()
        pipeline_stage = self._pipeline_stage_for(workflow_stage)
        await self.record_event(
            workflow_stage=workflow_stage,
            pipeline_stage=pipeline_stage,
            lead_id=lead_id,
            status=WorkflowStatus.running.value,
            metadata=metadata or {},
        )
        error_message: str | None = None
        failure_category: FailureCategory | None = None
        error_details: dict[str, Any] = {}
        try:
            yield
            status = WorkflowStatus.succeeded.value
        except Exception as exc:
            status = WorkflowStatus.failed.value
            error_message = str(exc) or f"({exc.__class__.__name__} with empty message)"
            failure_category = self.retry_policy.classify_failure(exc)
            error_details = {
                "exception_type": exc.__class__.__name__,
                "exception_module": exc.__class__.__module__,
                "traceback": traceback.format_exc(),
            }
            self.failures.append(
                {
                    "workflow_stage": workflow_stage,
                    "pipeline_stage": pipeline_stage.value,
                    "lead_id": str(lead_id) if lead_id else None,
                    "error_message": error_message,
                    "failure_category": failure_category.value,
                    **error_details,
                }
            )
            await self._rollback_session(
                reason="stage exception before failure event",
                workflow_stage=workflow_stage,
                lead_id=lead_id,
                error_message=error_message,
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            try:
                await self.record_event(
                    workflow_stage=workflow_stage,
                    pipeline_stage=pipeline_stage,
                    lead_id=lead_id,
                    status=status,
                    duration_ms=duration_ms,
                    error_message=error_message,
                    failure_category=failure_category,
                    metadata=(metadata or {}) | error_details,
                )
            except Exception as record_exc:
                logger.warning(
                    "Pipeline failure event recording failed",
                    extra=log_extra(
                        workflow_run_id=str(self.workflow_run_id),
                        correlation_id=self.correlation_id,
                        campaign_id=str(self.campaign_id) if self.campaign_id else None,
                        lead_id=str(lead_id) if lead_id else None,
                        workflow_stage=workflow_stage,
                        original_error_message=error_message,
                        original_error_details=error_details,
                        record_exception=str(record_exc),
                        recovery="failure event dropped after rollback attempt",
                    ),
                )

    async def run_resilient_stage(
        self,
        workflow_stage: str,
        operation: Callable[[], Awaitable[Any]],
        *,
        lead_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        pipeline_stage = self._pipeline_stage_for(workflow_stage)
        start = time.perf_counter()
        await self.record_event(
            workflow_stage=workflow_stage,
            pipeline_stage=pipeline_stage,
            lead_id=lead_id,
            status=WorkflowStatus.running.value,
            metadata=metadata or {},
        )
        execution = await self.retry_policy.run(
            operation,
            workflow_name=self.workflow_name,
            stage_name=workflow_stage,
            correlation_id=self.correlation_id,
            lead_id=lead_id,
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if execution.error_message is None:
            if execution.retry_count:
                await self.record_event(
                    workflow_stage=f"{workflow_stage}_retried",
                    pipeline_stage=pipeline_stage,
                    lead_id=lead_id,
                    status=WorkflowStatus.succeeded.value,
                    retry_count=execution.retry_count,
                    metadata={"recovered_after_retries": True, **(metadata or {})},
                )
            await self.record_event(
                workflow_stage=workflow_stage,
                pipeline_stage=pipeline_stage,
                lead_id=lead_id,
                status=WorkflowStatus.succeeded.value,
                duration_ms=duration_ms,
                retry_count=execution.retry_count,
                metadata=metadata or {},
            )
            return execution.value

        await self._rollback_session(
            reason="resilient stage recovery",
            workflow_stage=workflow_stage,
            lead_id=lead_id,
            error_message=execution.error_message,
        )
        failure_category = execution.failure_category or FailureCategory.unknown
        failure = {
            "workflow_stage": workflow_stage,
            "pipeline_stage": pipeline_stage.value,
            "lead_id": str(lead_id) if lead_id else None,
            "error_message": execution.error_message,
            "failure_category": failure_category.value,
            "retry_count": execution.retry_count,
            "retryable": execution.retryable,
            "dead_lettered": True,
        }
        self.failures.append(failure)
        await self.dead_letters.create_entry(
            workflow_name=self.workflow_name,
            pipeline_stage=pipeline_stage,
            failure_category=failure_category,
            error_message=execution.error_message,
            correlation_id=self.correlation_id,
            campaign_id=self.campaign_id,
            lead_id=lead_id,
            retry_count=execution.retry_count,
            retryable=execution.retryable,
            payload={"metadata": metadata or {}},
        )
        await self.record_event(
            workflow_stage=workflow_stage,
            pipeline_stage=pipeline_stage,
            lead_id=lead_id,
            status=WorkflowStatus.dead_lettered.value,
            duration_ms=duration_ms,
            error_message=execution.error_message,
            failure_category=failure_category,
            retry_count=execution.retry_count,
            retryable=execution.retryable,
            dead_lettered=True,
            metadata=metadata or {},
        )
        logger.warning(
            "Pipeline stage failed but execution continued",
            extra=log_extra(
                workflow_run_id=str(self.workflow_run_id),
                correlation_id=self.correlation_id,
                campaign_id=str(self.campaign_id) if self.campaign_id else None,
                lead_id=str(lead_id) if lead_id else None,
                workflow_stage=workflow_stage,
                failure_category=failure_category.value,
                retry_count=execution.retry_count,
                error_message=execution.error_message,
                recovery="session rollback completed",
            ),
        )
        return None

    async def record_event(
        self,
        *,
        workflow_stage: str,
        status: str,
        lead_id: uuid.UUID | None = None,
        pipeline_stage: PipelineStage | None = None,
        duration_ms: float = 0.0,
        error_message: str | None = None,
        failure_category: FailureCategory | None = None,
        retry_count: int = 0,
        retryable: bool = False,
        dead_lettered: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineEvent:
        event = PipelineEvent(
            workflow_run_id=self.workflow_run_id,
            campaign_id=self.campaign_id,
            lead_id=lead_id,
            workflow_stage=workflow_stage,
            pipeline_stage=pipeline_stage,
            correlation_id=self.correlation_id,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
            failure_category=failure_category,
            retry_count=retry_count,
            retryable=retryable,
            dead_lettered=dead_lettered,
            metadata=metadata or {},
        )
        await self.workflow_logs.create_log(
            WorkflowLog(
                campaign_id=self.campaign_id,
                lead_id=lead_id,
                workflow_name=self.workflow_name,
                correlation_id=self.correlation_id,
                pipeline_stage=pipeline_stage,
                status=WorkflowStatus(status),
                failure_category=failure_category,
                retry_count=retry_count,
                retryable=retryable,
                dead_lettered=dead_lettered,
                detail=f"{workflow_stage}:{status}",
                payload=event.model_dump(mode="json"),
            ),
        )
        await self.session.commit()
        logger.info("Pipeline event recorded", extra=log_extra(**event.model_dump(mode="json")))
        try:
            await redis_state.push_json(
                f"salesos:pipeline:{self.workflow_run_id}:events",
                event.model_dump(mode="json"),
                max_items=200,
                ttl_seconds=86400,
            )
            await redis_state.set_json(
                "salesos:pipeline:last_event",
                event.model_dump(mode="json"),
                ttl_seconds=86400,
            )
        except Exception as exc:
            logger.warning(
                "Pipeline event cache write failed",
                extra=log_extra(
                    workflow_run_id=str(self.workflow_run_id),
                    workflow_stage=workflow_stage,
                    error_message=str(exc),
                ),
            )
        return event

    async def _rollback_session(
        self,
        *,
        reason: str,
        workflow_stage: str,
        lead_id: uuid.UUID | None,
        error_message: str,
    ) -> None:
        try:
            await self.session.rollback()
            logger.warning(
                "Pipeline session rollback executed",
                extra=log_extra(
                    workflow_run_id=str(self.workflow_run_id),
                    correlation_id=self.correlation_id,
                    campaign_id=str(self.campaign_id) if self.campaign_id else None,
                    lead_id=str(lead_id) if lead_id else None,
                    workflow_stage=workflow_stage,
                    reason=reason,
                    error_message=error_message,
                ),
            )
        except Exception as rollback_exc:
            logger.error(
                "Pipeline session rollback failed",
                extra=log_extra(
                    workflow_run_id=str(self.workflow_run_id),
                    correlation_id=self.correlation_id,
                    campaign_id=str(self.campaign_id) if self.campaign_id else None,
                    lead_id=str(lead_id) if lead_id else None,
                    workflow_stage=workflow_stage,
                    reason=reason,
                    error_message=error_message,
                    rollback_error=str(rollback_exc),
                ),
            )

    @staticmethod
    def _pipeline_stage_for(workflow_stage: str) -> PipelineStage:
        lowered = workflow_stage.lower()
        if "scrape" in lowered:
            return PipelineStage.scrape
        if "normal" in lowered:
            return PipelineStage.normalize
        if "dedup" in lowered or "insert" in lowered:
            return PipelineStage.dedupe
        if "enrich" in lowered:
            return PipelineStage.enrich
        if "intelligence" in lowered or "review_signal" in lowered:
            return PipelineStage.intelligence
        if "score" in lowered or "qualif" in lowered:
            return PipelineStage.score
        if "analysis" in lowered:
            return PipelineStage.analyze
        if "personal" in lowered or "outreach" in lowered or "review" in lowered:
            return PipelineStage.outreach_generate
        if "follow" in lowered:
            return PipelineStage.follow_up
        if "reply" in lowered:
            return PipelineStage.reply_classify
        if "escalat" in lowered:
            return PipelineStage.escalate
        return PipelineStage.notify
