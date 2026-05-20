from __future__ import annotations

import unittest

from app.services.scrape_pipeline_service import ScrapePipelineService


class _FakeObserver:
    def __init__(self) -> None:
        self.failures: list[dict] = []
        self.events: list[dict] = []

    async def record_event(self, **kwargs):  # noqa: ANN003
        self.events.append(kwargs)
        return kwargs


class ScrapePipelineDegradationTests(unittest.IsolatedAsyncioTestCase):
    async def test_degraded_dependency_is_recorded_for_honest_partial_status(self) -> None:
        service = object.__new__(ScrapePipelineService)
        observer = _FakeObserver()

        await service._record_degraded_dependency_if_present(  # type: ignore[attr-defined]
            observer,
            workflow_stage="telegram_alert_degraded",
            dependency_result={"status": "degraded", "reason": "telegram down"},
        )

        self.assertEqual(len(observer.failures), 1)
        self.assertTrue(observer.failures[0]["degraded"])
        status = ScrapePipelineService._final_workflow_status(
            total_received=1,
            inserted=1,
            deduplicated=0,
            analyzed=1,
            personalized=1,
            invalid=0,
            errors=observer.failures,
            source_mode="fixture:test",
        )
        self.assertEqual(status, "partial")


if __name__ == "__main__":
    unittest.main()
