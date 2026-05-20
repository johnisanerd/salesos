from __future__ import annotations

import unittest

from app.services.scrape_pipeline_service import ScrapePipelineService


class ScrapePipelinePolicyTests(unittest.TestCase):
    def test_existing_lead_processing_respects_flag(self) -> None:
        disabled = ScrapePipelineService._decide_existing_lead_processing(
            created=False,
            process_existing_leads=False,
        )
        enabled = ScrapePipelineService._decide_existing_lead_processing(
            created=False,
            process_existing_leads=True,
        )

        self.assertFalse(disabled.reuse_existing)
        self.assertEqual(disabled.skip_reason, "process_existing_leads_disabled")
        self.assertTrue(enabled.reuse_existing)

    def test_cooldown_skip_detects_recent_outreach(self) -> None:
        self.assertTrue(ScrapePipelineService._should_skip_due_to_cooldown(object()))
        self.assertFalse(ScrapePipelineService._should_skip_due_to_cooldown(None))

    def test_final_workflow_status_becomes_partial_when_errors_exist(self) -> None:
        status = ScrapePipelineService._final_workflow_status(
            total_received=4,
            inserted=1,
            deduplicated=1,
            analyzed=1,
            personalized=0,
            invalid=1,
            errors=[{"workflow_stage": "lead_normalization", "error_message": "bad data"}],
            source_mode="fixture:malformed_leads",
        )
        self.assertEqual(status, "partial")

    def test_final_workflow_status_becomes_completed_without_errors(self) -> None:
        status = ScrapePipelineService._final_workflow_status(
            total_received=2,
            inserted=0,
            deduplicated=2,
            analyzed=2,
            personalized=0,
            invalid=0,
            errors=[],
            source_mode="fixture:duplicate_leads",
        )
        self.assertEqual(status, "completed")


if __name__ == "__main__":
    unittest.main()
