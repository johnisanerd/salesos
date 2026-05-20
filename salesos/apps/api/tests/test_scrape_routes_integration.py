from __future__ import annotations

import asyncio
import unittest
import uuid
from unittest.mock import patch

import httpx

from app.api.routes import leads as lead_routes
from app.main import app
from app.schemas.lead import ScrapePipelineResponse, ScrapeRequest
from app.services import scrape_job_service as job_module
from app.services.scrape_job_service import ScrapeJobService


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class ScrapeRouteIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        async with job_module._MEMORY_LOCK:
            job_module._MEMORY_JOB_STATE.clear()

    async def test_scrape_route_returns_job_id_and_polling_tracks_completion(self) -> None:
        service = ScrapeJobService()

        async def fake_run(self, payload: ScrapeRequest) -> ScrapePipelineResponse:  # noqa: ARG001
            await asyncio.sleep(0.02)
            return ScrapePipelineResponse(
                workflow_run_id=uuid.uuid4(),
                source_mode="fixture:test",
                workflow_status="completed",
                total_received=1,
                inserted=1,
                deduplicated=0,
                reused_existing=0,
                analyzed=1,
                personalized=1,
                outreach_generated=1,
                skipped_due_to_cooldown=0,
                invalid=0,
                campaign_id=None,
                summary="completed",
                errors=[],
            )

        with (
            patch.object(lead_routes, "jobs", service),
            patch.object(job_module, "AsyncSessionFactory", new=lambda: _FakeSessionContext()),
            patch.object(job_module.ScrapePipelineService, "run", new=fake_run),
        ):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/leads/scrape",
                    json={"query": "marketing agency", "location": "Austin, TX", "fixture_name": "sample_leads"},
                )
                self.assertEqual(response.status_code, 202)
                accepted = response.json()
                self.assertEqual(accepted["status"], "pending")

                job_id = accepted["job_id"]
                immediate = await client.get(f"/api/leads/scrape/{job_id}")
                self.assertEqual(immediate.status_code, 200)
                self.assertIn(immediate.json()["status"], {"pending", "running", "completed"})

                final = await self._wait_for_terminal_status(client, job_id)
                self.assertEqual(final["status"], "completed")
                self.assertEqual(final["result"]["workflow_status"], "completed")

    async def test_unknown_job_polling_returns_404(self) -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(f"/api/leads/scrape/{uuid.uuid4()}")
            self.assertEqual(response.status_code, 404)

    async def _wait_for_terminal_status(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        *,
        timeout_seconds: float = 2.0,
    ) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/api/leads/scrape/{job_id}")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            if payload["status"] in {"completed", "partial", "failed"}:
                return payload
            await asyncio.sleep(0.01)
        self.fail(f"Job {job_id} did not reach a terminal state within {timeout_seconds}s")


if __name__ == "__main__":
    unittest.main()
