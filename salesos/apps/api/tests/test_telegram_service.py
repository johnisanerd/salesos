from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from app.services.telegram_service import TelegramAlertService


class _ExplodingAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise httpx.ConnectError("telegram down")


class TelegramAlertServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_alert_returns_degraded_payload_when_delivery_fails(self) -> None:
        service = TelegramAlertService()

        with patch("app.services.telegram_service.httpx.AsyncClient", return_value=_ExplodingAsyncClient()):
            result = await service.send_alert(title="test", message="message")

        self.assertEqual(result["status"], "degraded")
        self.assertIn("telegram down", result["reason"])


if __name__ == "__main__":
    unittest.main()
