from __future__ import annotations

import unittest

from app.models.enums import LeadPersonalizationTier
from app.services.lead_scoring_service import LeadScoringService


class LeadScoringServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LeadScoringService()

    def test_high_quality_lead_scores_for_deep_personalization(self) -> None:
        result = self.service.score_lead(
            business_name="River City SEO Co",
            website="https://rivercityseo.co",
            email="hello@rivercityseo.co",
            phone="+15550101212",
            city="Austin",
            category="seo agency",
            metadata={"source_payload": {"review_count": 54, "rating": 4.8}},
            query="seo agency",
            location="Austin, TX",
        )

        self.assertGreaterEqual(result.score, 70)
        self.assertEqual(result.personalization_tier, LeadPersonalizationTier.high)
        self.assertIn("website_present", result.reasons)

    def test_low_quality_lead_scores_for_skip(self) -> None:
        result = self.service.score_lead(
            business_name="Budget Local Services",
            website=None,
            email=None,
            phone=None,
            city=None,
            category="services",
            metadata={"source_payload": {"review_count": 0, "rating": 0}},
            query="marketing agency",
            location="Austin, TX",
        )

        self.assertLess(result.score, 45)
        self.assertEqual(result.personalization_tier, LeadPersonalizationTier.low)

    def test_review_signal_severity_boosts_priority(self) -> None:
        result = self.service.score_lead(
            business_name="Northwind Growth Studio",
            website="https://northwindgrowth.com",
            email=None,
            phone="+15550101111",
            city="Austin",
            category="marketing agency",
            metadata={
                "source_payload": {"review_count": 48, "rating": 4.2},
                "review_signal_summary": {
                    "severity": 82,
                    "categories": ["missed_calls", "no_followup"],
                    "operational_summary": "Recent reviews for Northwind Growth Studio repeatedly mention missed calls.",
                    "generated_hook": "That usually means inbound demand is leaking before staff can turn enquiries into booked work.",
                },
            },
            query="marketing agency",
            location="Austin, TX",
        )

        self.assertGreaterEqual(result.score, 70)
        self.assertEqual(result.personalization_tier, LeadPersonalizationTier.high)
        self.assertIn("review_signal_high_severity", result.reasons)

    def test_business_analysis_boosts_explainable_score(self) -> None:
        result = self.service.score_lead(
            business_name="Signal Roofing",
            website="https://signalroofing.example",
            email="ops@signalroofing.example",
            phone="+15550109999",
            city="Austin",
            category="roofing contractor",
            metadata={
                "source_payload": {"review_count": 12, "rating": 4.6},
                "business_analysis": {
                    "website_exists": True,
                    "ssl_enabled": True,
                    "mobile_responsive": True,
                    "social_links": ["https://instagram.com/signalroofing"],
                    "cta_detected": True,
                    "seo_title_present": True,
                    "seo_description_present": True,
                    "score_inputs": {
                        "website_exists": 1,
                        "ssl_enabled": 1,
                        "mobile_responsive": 1,
                        "social_links": 1,
                        "cta_detected": 1,
                        "seo_metadata": 1,
                    },
                },
            },
            query="roofing contractor",
            location="Austin, TX",
        )

        component_names = {component.name for component in result.components}
        self.assertIn("mobile_responsive", component_names)
        self.assertIn("cta_detected", component_names)
        self.assertIn("seo_metadata", component_names)
        self.assertGreaterEqual(result.score, 70)


if __name__ == "__main__":
    unittest.main()
