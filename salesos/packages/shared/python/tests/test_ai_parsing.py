from __future__ import annotations

import unittest

from pydantic import BaseModel

from salesos_shared.ai_parsing import (
    extract_first_json_object,
    recover_structured_fields,
    strip_markdown_fences,
    validate_response_payload,
)


class ExampleResponse(BaseModel):
    score: float
    summary: str


class AIParsingTests(unittest.TestCase):
    def test_strip_markdown_fences_removes_json_wrapper(self) -> None:
        raw_text = "```json\n{\"score\": 0.8}\n```"
        self.assertEqual(strip_markdown_fences(raw_text), "{\"score\": 0.8}")

    def test_extract_first_json_object_ignores_prose_before_and_after(self) -> None:
        raw_text = 'Here is the result:\n```json\n{"score": 0.8, "summary": "ok"}\n```\nThanks!'
        result = extract_first_json_object(raw_text)

        self.assertEqual(result.payload, {"score": 0.8, "summary": "ok"})
        self.assertEqual(result.json_text, '{"score": 0.8, "summary": "ok"}')

    def test_extract_first_json_object_skips_malformed_candidate_and_finds_next(self) -> None:
        raw_text = 'bad {"score": } next {"score": 0.9, "summary": "usable"}'
        result = extract_first_json_object(raw_text)

        self.assertEqual(result.payload, {"score": 0.9, "summary": "usable"})
        self.assertTrue(any(error.code == "malformed_json" for error in result.errors))

    def test_extract_first_json_object_returns_structured_error_when_missing(self) -> None:
        result = extract_first_json_object("No JSON here.")

        self.assertIsNone(result.payload)
        self.assertTrue(any(error.code == "json_object_not_found" for error in result.errors))

    def test_validate_response_payload_reports_missing_required_fields(self) -> None:
        result = validate_response_payload({"score": 0.4}, ExampleResponse)

        self.assertIsNone(result.value)
        self.assertTrue(any(error.field == "summary" for error in result.errors))

    def test_validate_response_payload_reports_invalid_types(self) -> None:
        result = validate_response_payload({"score": "high", "summary": "ok"}, ExampleResponse)

        self.assertIsNone(result.value)
        self.assertTrue(any(error.field == "score" for error in result.errors))

    def test_recover_structured_fields_reads_colon_separated_output(self) -> None:
        raw_text = "observation: CTA is buried on mobile\nproblem: quote intent leaks\noutreach_hook: clearer CTA could help"
        result = recover_structured_fields(raw_text, ["observation", "problem", "outreach_hook"])

        self.assertEqual(
            result,
            {
                "observation": "CTA is buried on mobile",
                "problem": "quote intent leaks",
                "outreach_hook": "clearer CTA could help",
            },
        )


if __name__ == "__main__":
    unittest.main()
