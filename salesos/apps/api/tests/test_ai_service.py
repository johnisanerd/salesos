from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.services.ai_service import AIService, LeadAnalysis, OutreachPersonalization
from salesos_shared.ai import AIProviderError


class AIServiceTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_lead_timeout_falls_back_with_timeout_diagnostics(self) -> None:
        service = AIService()

        async def slow_generate(**kwargs):  # noqa: ANN003
            await asyncio.sleep(0.05)
            return LeadAnalysis(score=80, observation="obs", problem="prob", outreach_hook="hook")

        with patch.object(service.generator, "generate", side_effect=slow_generate), patch(
            "app.services.ai_service.settings.ollama_generation_timeout_seconds",
            0.01,
        ):
            result = await service.analyze_lead(
                "test prompt",
                business_name="Northwind",
                context="marketing agency in Austin",
            )

        self.assertTrue(result.generation_metadata["fallback_used"])
        self.assertIn("generation_timeout", result.generation_metadata["quality_issues"])

    async def test_analyze_lead_provider_failure_falls_back_cleanly(self) -> None:
        service = AIService()

        async def failing_generate(**kwargs):  # noqa: ANN003
            raise AIProviderError("ollama unreachable", code="provider_request_failed")

        with patch.object(service.generator, "generate", side_effect=failing_generate):
            result = await service.analyze_lead(
                "test prompt",
                business_name="Northwind",
                context="marketing agency in Austin",
            )

        self.assertTrue(result.generation_metadata["fallback_used"])
        self.assertIn("provider_request_failed", result.generation_metadata["quality_issues"])

    async def test_generate_outreach_timeout_falls_back_with_usable_message(self) -> None:
        service = AIService()
        analysis = LeadAnalysis(
            score=70,
            observation="Northwind has a mobile CTA issue.",
            problem="Mobile visitors likely hesitate before booking.",
            outreach_hook="A sharper mobile CTA would reduce leakage.",
        )

        async def slow_generate(**kwargs):  # noqa: ANN003
            await asyncio.sleep(0.05)
            return OutreachPersonalization(
                observation=analysis.observation,
                problem=analysis.problem,
                outreach_hook=analysis.outreach_hook,
                subject="test",
                message="test",
            )

        with patch.object(service.generator, "generate", side_effect=slow_generate), patch(
            "app.services.ai_service.settings.ollama_generation_timeout_seconds",
            0.01,
        ):
            result = await service.generate_outreach(
                "test prompt",
                business_name="Northwind",
                context="marketing agency in Austin",
                analysis=analysis,
            )

        self.assertTrue(result.generation_metadata["fallback_used"])
        self.assertIn("generation_timeout", result.generation_metadata["quality_issues"])
        self.assertIn("Northwind", result.message)


if __name__ == "__main__":
    unittest.main()
