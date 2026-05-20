from __future__ import annotations

import asyncio
import unittest
import uuid
from datetime import UTC, datetime

from app.models.enums import LeadState, LeadStatus
from app.models.lead import Lead
from app.services.review_signal_service import ReviewSignalService


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, _statement):  # noqa: ANN001
        class Result:
            @staticmethod
            def scalar_one_or_none():
                return None

        return Result()


class ExplodingAIService:
    async def refine_review_signal(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("ollama unavailable")


class ReviewSignalServiceTests(unittest.TestCase):
    def _build_lead(self) -> Lead:
        return Lead(
            id=uuid.uuid4(),
            business_name="Northwind Growth Studio",
            source="google_maps",
            status=LeadStatus.new,
            lifecycle_state=LeadState.DISCOVERED,
            state_updated_at=datetime.now(UTC),
            state_timestamps={LeadState.DISCOVERED.value: datetime.now(UTC).isoformat()},
            normalized_fingerprint="review-signal-test",
            metadata_json={},
        )

    def test_detects_high_severity_review_signals(self) -> None:
        async def run_test() -> None:
            service = ReviewSignalService(FakeSession(), ai_service=ExplodingAIService())  # type: ignore[arg-type]
            lead = self._build_lead()
            assessment = await service.analyze_and_store(
                lead=lead,
                business_name=lead.business_name,
                business_category="marketing agency",
                reviews=[
                    {
                        "text": "They never answered our calls and no one followed up after promising a callback.",
                        "rating": 1,
                        "timestamp": "2026-05-10T10:00:00Z",
                    },
                    {
                        "text": "Slow to respond and we were still waiting days later.",
                        "rating": 2,
                        "timestamp": "2026-05-04T09:30:00Z",
                    },
                ],
            )

            self.assertIsNotNone(assessment)
            assert assessment is not None
            self.assertGreaterEqual(assessment.severity, 75)
            self.assertIn("missed_calls", assessment.categories)
            self.assertIn("review_signal_summary", lead.metadata_json)
            self.assertEqual(lead.metadata_json["review_signal_summary"]["severity"], assessment.severity)
            self.assertIn("evidence_snippets", lead.metadata_json["review_signal_summary"])
            self.assertGreaterEqual(
                len(lead.metadata_json["review_signal_summary"]["evidence_snippets"]),
                1,
            )
            self.assertIn(
                "never answered our calls",
                lead.metadata_json["review_signal_summary"]["evidence_snippets"][0],
            )

        asyncio.run(run_test())

    def test_malformed_reviews_are_ignored(self) -> None:
        async def run_test() -> None:
            service = ReviewSignalService(FakeSession(), ai_service=ExplodingAIService())  # type: ignore[arg-type]
            lead = self._build_lead()
            assessment = await service.analyze_and_store(
                lead=lead,
                business_name=lead.business_name,
                business_category="marketing agency",
                reviews=[
                    {"text": "", "rating": 1},
                    {"review_text": None, "rating": 2},
                ],
            )

            self.assertIsNone(assessment)

        asyncio.run(run_test())

    def test_ai_refinement_failure_falls_back_to_heuristics(self) -> None:
        async def run_test() -> None:
            session = FakeSession()
            service = ReviewSignalService(session, ai_service=ExplodingAIService())  # type: ignore[arg-type]
            lead = self._build_lead()
            assessment = await service.analyze_and_store(
                lead=lead,
                business_name=lead.business_name,
                business_category="marketing agency",
                reviews=[
                    {
                        "text": "No answer when we called, then they never followed up after the voicemail.",
                        "rating": 1,
                        "timestamp": "2026-05-12T08:00:00Z",
                    },
                ],
            )

            self.assertIsNotNone(assessment)
            assert assessment is not None
            self.assertFalse(assessment.ai_refined)
            self.assertIn("Recent reviews for", assessment.operational_summary)
            self.assertGreaterEqual(session.commits, 1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
