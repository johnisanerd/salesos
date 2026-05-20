from urllib.parse import urlparse

from salesos_shared.logging import get_logger, log_extra

from bot.config import settings


logger = get_logger(__name__)


def validate_startup_settings() -> None:
    warnings: list[str] = []
    if settings.telegram_bot_token in {"", "replace-me"}:
        warnings.append("TELEGRAM_BOT_TOKEN is not configured; alerts will be cached but not delivered")
    if not settings.telegram_alert_chats:
        warnings.append("TELEGRAM_ALERT_CHAT_IDS is empty; no chat fan-out targets are configured")
    if telegram_mode() == "webhook":
        if settings.telegram_webhook_secret in {"", "replace-me"}:
            warnings.append("TELEGRAM_WEBHOOK_SECRET is not configured; webhook mode requires a non-default secret")
        if not settings.telegram_base_url.strip():
            warnings.append("TELEGRAM_BASE_URL is required when TELEGRAM_USE_WEBHOOKS=true")
        elif not _valid_public_webhook_base_url(settings.telegram_base_url):
            warnings.append("TELEGRAM_BASE_URL must be a public HTTPS URL when webhook mode is enabled")

    for warning in warnings:
        logger.warning(warning, extra=log_extra(service="telegram-bot", environment=settings.environment))

    if settings.startup_strict_validation and warnings:
        raise RuntimeError("Telegram bot startup validation failed in strict mode")


def telegram_mode() -> str:
    if settings.telegram_use_webhooks:
        return "webhook"
    if settings.environment == "production" and settings.telegram_base_url.strip():
        return "webhook"
    return "polling"


def telegram_webhook_url() -> str:
    return f"{settings.telegram_base_url.rstrip('/')}/telegram/webhook"


def _valid_public_webhook_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"}:
        return False
    return True
