from __future__ import annotations

import unittest

from salesos_shared.logging import log_extra


class LoggingSanitizationTests(unittest.TestCase):
    def test_log_extra_redacts_secrets_and_tokenized_urls(self) -> None:
        payload = log_extra(
            api_token="secret-value",
            target="https://api.example.com/resource?token=abc123&safe=yes",
            nested={"password": "hidden", "note": "ok"},
        )["extra"]

        self.assertEqual(payload["api_token"], "[REDACTED]")
        self.assertEqual(payload["nested"]["password"], "[REDACTED]")
        self.assertIn("token=%5BREDACTED%5D", payload["target"])
        self.assertIn("safe=yes", payload["target"])


if __name__ == "__main__":
    unittest.main()
