from __future__ import annotations

import asyncio
import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.schemas.lead import ScrapePipelineResponse, ScrapeRequest
from app.services import scrape_job_service as job_module
from app.services.scrape_job_service import ScrapeJobService


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class ScrapeJobServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        async with job_module._MEMORY_LOCK:
            job_module._MEMORY_JOB_STATE.clear()

    async def test_successful_job_lifecycle_reaches_completed(self) -> None:
        async def fake_run(_pipeline, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(0.02)
            return ScrapeJobServiceTests._build_response("completed")

        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX", fixture_name="sample_leads")

        with (
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
        ):
            job = await service.create_job(payload)
            pending = await service.get_job(job.job_id)
            self.assertIsNotNone(pending)
            assert pending is not None
            self.assertEqual(pending.status, "pending")

            task = asyncio.create_task(service.run_job(job.job_id, payload))
            running = await self._wait_for_status(service, job.job_id, {"running"})
            self.assertIsNotNone(running.started_at)
            await task

            completed = await self._wait_for_status(service, job.job_id, {"completed"})
            self.assertIsNotNone(completed.completed_at)
            assert completed.result is not None
            self.assertEqual(completed.result.workflow_status, "completed")

    async def test_partial_job_lifecycle_reaches_partial(self) -> None:
        async def fake_run(_pipeline, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(0.01)
            return ScrapeJobServiceTests._build_response(
                "partial",
                errors=[{"workflow_stage": "lead_normalization", "error_message": "bad data"}],
                invalid=1,
            )

        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX", fixture_name="malformed_leads")

        with (
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
        ):
            job = await service.create_job(payload)
            task = asyncio.create_task(service.run_job(job.job_id, payload))
            await task
            final = await self._wait_for_status(service, job.job_id, {"partial"})
            self.assertEqual(final.status, "partial")
            assert final.result is not None
            self.assertEqual(final.result.workflow_status, "partial")
            self.assertEqual(len(final.result.errors), 1)

    async def test_failed_job_lifecycle_reaches_failed(self) -> None:
        async def fake_run(_pipeline, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(0.01)
            raise RuntimeError("pipeline exploded")

        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX")

        with (
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
        ):
            job = await service.create_job(payload)
            task = asyncio.create_task(service.run_job(job.job_id, payload))
            await task
            final = await self._wait_for_status(service, job.job_id, {"failed"})
            self.assertEqual(final.status, "failed")
            assert final.error is not None
            self.assertEqual(final.error["code"], "job_execution_failed")
            self.assertIn("pipeline exploded", final.error["message"])

    async def test_job_timeout_marks_failed_honestly(self) -> None:
        async def fake_run(_pipeline, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(0.05)
            return ScrapeJobServiceTests._build_response("completed")

        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX")

        with (
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
            patch.object(job_module.settings, "scrape_job_timeout_seconds", 0.01),
        ):
            job = await service.create_job(payload)
            task = asyncio.create_task(service.run_job(job.job_id, payload))
            await task
            final = await self._wait_for_status(service, job.job_id, {"failed"})
            assert final.error is not None
            self.assertEqual(final.error["code"], "job_timeout")

    async def test_job_state_survives_redis_failures_with_memory_fallback(self) -> None:
        async def fake_run(_pipeline, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(0.01)
            return ScrapeJobServiceTests._build_response("completed")

        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX")

        with (
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
            patch.object(job_module.redis_state, "set_json", new=AsyncMock(side_effect=RuntimeError("redis down"))),
            patch.object(job_module.redis_state, "get_json", new=AsyncMock(side_effect=RuntimeError("redis down"))),
        ):
            job = await service.create_job(payload)
            task = asyncio.create_task(service.run_job(job.job_id, payload))
            await task
            final = await self._wait_for_status(service, job.job_id, {"completed"})
            self.assertEqual(final.status, "completed")

    async def test_sweep_stale_jobs_marks_running_jobs_failed(self) -> None:
        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX")
        job = await service.create_job(payload)
        stale_started_at = datetime.now(UTC).isoformat()
        await service._transition_job(job.job_id, "running", started_at=stale_started_at, error=None)

        with patch.object(job_module.settings, "scrape_job_stale_timeout_seconds", 0):
            marked = await service.sweep_stale_jobs()

        self.assertEqual(marked, 1)
        final = await service.get_job(job.job_id)
        assert final is not None
        self.assertEqual(final.status, "failed")
        assert final.error is not None
        self.assertEqual(final.error["code"], "job_stale_timeout")

    async def test_cancelled_job_transitions_to_failed(self) -> None:
        async def fake_run(_pipeline, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(1)
            return ScrapeJobServiceTests._build_response("completed")

        service = ScrapeJobService()
        payload = ScrapeRequest(query="marketing agency", location="Austin, TX")

        with (
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
        ):
            job = await service.create_job(payload)
            task = asyncio.create_task(service.run_job(job.job_id, payload))
            await self._wait_for_status(service, job.job_id, {"running"})
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        final = await self._wait_for_status(service, job.job_id, {"failed"})
        assert final.error is not None
        self.assertEqual(final.error["code"], "job_cancelled")

    async def _wait_for_status(
        self,
        service: ScrapeJobService,
        job_id: uuid.UUID,
        expected_statuses: set[str],
        *,
        timeout_seconds: float = 2.0,
    ):
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            job = await service.get_job(job_id)
            if job is not None and job.status in expected_statuses:
                return job
            await asyncio.sleep(0.01)
        self.fail(f"Job {job_id} did not reach one of {sorted(expected_statuses)} within {timeout_seconds}s")

    @staticmethod
    def _build_response(
        workflow_status: str,
        *,
        errors: list[dict] | None = None,
        invalid: int = 0,
    ) -> ScrapePipelineResponse:
        return ScrapePipelineResponse(
            workflow_run_id=uuid.uuid4(),
            source_mode="fixture:test",
            workflow_status=workflow_status,
            total_received=1,
            inserted=1,
            deduplicated=0,
            reused_existing=0,
            analyzed=1,
            personalized=1,
            outreach_generated=1,
            skipped_due_to_cooldown=0,
            invalid=invalid,
            campaign_id=None,
            summary="test job",
            errors=errors or [],
        )


if __name__ == "__main__":
    unittest.main()
