import httpx

from app.core.settings import settings
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


class TelegramAlertService:
    async def send_alert(
        self,
        *,
        title: str,
        message: str,
        level: str = "info",
        metadata: dict | None = None,
    ) -> dict:
        url = f"{settings.telegram_bot_internal_url.rstrip('/')}/internal/alerts"
        payload = {
            "title": title,
            "message": message,
            "level": level,
            "metadata": metadata or {},
        }
        headers = {"X-Internal-Service-Token": settings.internal_service_token}
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                logger.warning(
                    "Telegram bot alert dispatch failed",
                    extra=log_extra(service="api", target=url, error=str(exc)),
                )
                return {"status": "degraded", "reason": str(exc)}
