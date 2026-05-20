from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from salesos_shared.retry import RetryError, retry_async


class RetryAsyncTests(unittest.TestCase):
    def test_wait_for_timeout_is_retried_and_wrapped(self) -> None:
        attempts: list[int] = []

        async def operation() -> str:
            attempts.append(1)
            await asyncio.sleep(0.02)
            return "ok"

        async def run_test() -> None:
            with self.assertRaises(RetryError):
                await retry_async(operation, attempts=2, timeout_seconds=0.001, backoff_seconds=0)

        asyncio.run(run_test())
        self.assertEqual(len(attempts), 2)

    def test_retry_logging_includes_attempt_reason_and_delay(self) -> None:
        attempts: list[int] = []

        async def operation() -> str:
            attempts.append(1)
            raise TimeoutError("slow dependency")

        async def run_test() -> None:
            with self.assertRaises(RetryError), patch("salesos_shared.retry.logger.warning") as warning:
                await retry_async(
                    operation,
                    attempts=2,
                    timeout_seconds=0.01,
                    backoff_seconds=0,
                    retry_context={"job_id": "job-123", "stage": "ollama_analysis"},
                )
            return warning

        warning = asyncio.run(run_test())
        warning.assert_called_once()
        _, kwargs = warning.call_args
        extra = kwargs["extra"]["extra"]
        self.assertEqual(extra["retry_attempt"], 1)
        self.assertEqual(extra["retry_delay_seconds"], 0)
        self.assertEqual(extra["job_id"], "job-123")
        self.assertEqual(extra["stage"], "ollama_analysis")
        self.assertIn("slow dependency", extra["retry_failure_reason"])


if __name__ == "__main__":
    unittest.main()
