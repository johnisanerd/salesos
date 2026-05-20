from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import UTC, datetime
from typing import Any

from app.clients.redis import redis_state
from app.core.settings import settings
from app.db.session import AsyncSessionFactory
from app.schemas.lead import (
    JobStatus,
    ScrapeJobAccepted,
    ScrapeJobStatusResponse,
    ScrapePipelineResponse,
    ScrapeRequest,
)
from app.services.scrape_pipeline_service import ScrapePipelineService
from salesos_shared.logging import get_logger, log_extra, request_id_context


logger = get_logger(__name__)

_JOB_TTL_SECONDS = 86400
_MEMORY_JOB_STATE: dict[str, dict[str, Any]] = {}
_MEMORY_LOCK = asyncio.Lock()


class ScrapeJobService:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._cleanup_guard = asyncio.Lock()

    async def start_job(self, payload: ScrapeRequest) -> ScrapeJobAccepted:
        await self.sweep_stale_jobs()
        job = await self.create_job(payload)
        task = asyncio.create_task(self.run_job(job.job_id, payload), name=f"salesos-scrape-job-{job.job_id}")
        self._tasks.add(task)
        task.add_done_callback(self._finalize_task)
        return job

    async def create_job(self, payload: ScrapeRequest) -> ScrapeJobAccepted:
        job_id = uuid.uuid4()
        correlation_id = str(uuid.uuid4())
        state = {
            "job_id": str(job_id),
            "correlation_id": correlation_id,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": None,
            "completed_at": None,
            "payload": payload.model_dump(mode="json"),
            "result": None,
            "error": None,
        }
        await self._store_job_state(job_id, state)
        logger.info(
            "Scrape job queued",
            extra=log_extra(service="api", job_id=str(job_id), status="pending"),
        )
        return ScrapeJobAccepted(job_id=job_id, status="pending")

    async def get_job(self, job_id: uuid.UUID) -> ScrapeJobStatusResponse | None:
        await self.sweep_stale_jobs()
        state = await self._get_job_state(job_id)
        if state is None:
            return None
        return self._parse_job_state(state)

    async def start_cleanup_loop(self) -> None:
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="salesos-scrape-job-cleaner")

    async def stop_cleanup_loop(self) -> None:
        if self._cleanup_task is None:
            return
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        self._cleanup_task = None

    async def run_job(self, job_id: uuid.UUID, payload: ScrapeRequest) -> None:
        state = await self._get_job_state(job_id)
        correlation_id = (state or {}).get("correlation_id") or str(job_id)
        request_id_context.set(correlation_id)
        await self._transition_job(job_id, "running", started_at=datetime.now(UTC).isoformat(), error=None)
        try:
            async with AsyncSessionFactory() as session:
                result = await asyncio.wait_for(
                    ScrapePipelineService(session).run(payload),
                    timeout=settings.scrape_job_timeout_seconds,
                )
            final_status: JobStatus = self._job_status_from_pipeline(result)
            await self._transition_job(
                job_id,
                final_status,
                completed_at=datetime.now(UTC).isoformat(),
                result=result.model_dump(mode="json"),
                error=None,
            )
            logger.info(
                "Scrape job completed",
                extra=log_extra(
                    service="api",
                    job_id=str(job_id),
                    status=final_status,
                    workflow_run_id=str(result.workflow_run_id),
                    workflow_status=result.workflow_status,
                ),
            )
        except asyncio.TimeoutError as exc:
            error = self._build_error_payload(
                exc,
                code="job_timeout",
                timeout_seconds=settings.scrape_job_timeout_seconds,
            )
            await self._transition_job(
                job_id,
                "failed",
                completed_at=datetime.now(UTC).isoformat(),
                error=error,
            )
            logger.error(
                "Scrape job timed out",
                extra=log_extra(service="api", job_id=str(job_id), error=error),
            )
        except asyncio.CancelledError as exc:
            error = self._build_error_payload(exc, code="job_cancelled")
            await self._transition_job(
                job_id,
                "failed",
                completed_at=datetime.now(UTC).isoformat(),
                error=error,
            )
            logger.warning(
                "Scrape job cancelled",
                extra=log_extra(service="api", job_id=str(job_id), error=error),
            )
            raise
        except Exception as exc:
            error = self._build_error_payload(exc, code="job_execution_failed")
            await self._transition_job(
                job_id,
                "failed",
                completed_at=datetime.now(UTC).isoformat(),
                error=error,
            )
            logger.error(
                "Scrape job failed",
                extra=log_extra(service="api", job_id=str(job_id), error=error),
            )

    def _finalize_task(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Unhandled scrape job task failure")

    @staticmethod
    def _job_status_from_pipeline(result: ScrapePipelineResponse) -> JobStatus:
        if result.workflow_status == "completed":
            return "completed"
        if result.workflow_status == "partial":
            return "partial"
        return "failed"

    async def _transition_job(self, job_id: uuid.UUID, status: JobStatus, **updates: Any) -> None:
        current = await self._get_job_state(job_id)
        if current is None:
            return
        previous_status = current.get("status")
        current.update({"status": status, **updates})
        await self._store_job_state(job_id, current)
        logger.info(
            "Scrape job state transitioned",
            extra=log_extra(
                service="api",
                job_id=str(job_id),
                previous_status=previous_status,
                status=status,
                lifecycle_transition=f"{previous_status}_to_{status}" if previous_status else status,
            ),
        )

    async def _store_job_state(self, job_id: uuid.UUID, state: dict[str, Any]) -> None:
        key = self._job_key(job_id)
        try:
            await redis_state.set_json(key, state, ttl_seconds=_JOB_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "Redis job state write failed; using in-memory fallback",
                extra=log_extra(service="api", job_id=str(job_id), error=str(exc)),
            )
        async with _MEMORY_LOCK:
            _MEMORY_JOB_STATE[key] = dict(state)

    async def _get_job_state(self, job_id: uuid.UUID) -> dict[str, Any] | None:
        key = self._job_key(job_id)
        try:
            state = await redis_state.get_json(key)
            if state is not None:
                async with _MEMORY_LOCK:
                    _MEMORY_JOB_STATE[key] = dict(state)
                return state
        except Exception as exc:
            logger.warning(
                "Redis job state read failed; using in-memory fallback",
                extra=log_extra(service="api", job_id=str(job_id), error=str(exc)),
            )
        async with _MEMORY_LOCK:
            cached = _MEMORY_JOB_STATE.get(key)
            return dict(cached) if cached is not None else None

    @staticmethod
    def _parse_job_state(state: dict[str, Any]) -> ScrapeJobStatusResponse:
        result_payload = state.get("result")
        return ScrapeJobStatusResponse(
            job_id=uuid.UUID(state["job_id"]),
            status=state["status"],
            created_at=datetime.fromisoformat(state["created_at"]),
            started_at=datetime.fromisoformat(state["started_at"]) if state.get("started_at") else None,
            completed_at=datetime.fromisoformat(state["completed_at"]) if state.get("completed_at") else None,
            payload=state.get("payload") or {},
            result=ScrapePipelineResponse.model_validate(result_payload) if result_payload else None,
            error=state.get("error"),
        )

    async def list_jobs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        await self.sweep_stale_jobs()
        async with _MEMORY_LOCK:
            values = list(_MEMORY_JOB_STATE.values())
        values.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return values[:limit]

    @staticmethod
    def _job_key(job_id: uuid.UUID) -> str:
        return f"salesos:scrape_jobs:{job_id}"

    @staticmethod
    def _build_error_payload(exc: BaseException, *, code: str, **extra: Any) -> dict[str, Any]:
        return {
            "code": code,
            "message": str(exc) or f"({exc.__class__.__name__} with empty message)",
            "exception_type": exc.__class__.__name__,
            "exception_module": exc.__class__.__module__,
            "traceback": traceback.format_exc(),
            **extra,
        }

    async def _cleanup_loop(self) -> None:
        interval_seconds = max(5.0, min(settings.scrape_job_stale_timeout_seconds / 3, 30.0))
        while True:
            try:
                await self.sweep_stale_jobs()
            except Exception:
                logger.exception("Scrape job stale cleanup iteration failed")
            await asyncio.sleep(interval_seconds)

    async def sweep_stale_jobs(self) -> int:
        async with self._cleanup_guard:
            stale_keys: list[str] = []
            now = datetime.now(UTC)
            async with _MEMORY_LOCK:
                snapshot = {key: dict(value) for key, value in _MEMORY_JOB_STATE.items()}

            for key, state in snapshot.items():
                if state.get("status") != "running":
                    continue
                started_at_raw = state.get("started_at")
                if not started_at_raw:
                    continue
                started_at = datetime.fromisoformat(started_at_raw)
                age_seconds = max((now - started_at).total_seconds(), 0.0)
                if age_seconds >= settings.scrape_job_stale_timeout_seconds:
                    stale_keys.append(key)

            for key in stale_keys:
                job_id = uuid.UUID(key.rsplit(":", 1)[-1])
                error = {
                    "code": "job_stale_timeout",
                    "message": "Job exceeded stale running timeout and was failed by the sweeper.",
                    "stale_timeout_seconds": settings.scrape_job_stale_timeout_seconds,
                    "detected_at": now.isoformat(),
                }
                await self._transition_job(
                    job_id,
                    "failed",
                    completed_at=now.isoformat(),
                    error=error,
                )
                logger.error(
                    "Scrape job marked failed by stale-job sweeper",
                    extra=log_extra(
                        service="api",
                        job_id=str(job_id),
                        status="failed",
                        failure_reason="job_stale_timeout",
                        stale_timeout_seconds=settings.scrape_job_stale_timeout_seconds,
                        lifecycle_transition="running_to_failed",
                    ),
                )
            return len(stale_keys)
