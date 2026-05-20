from telegram import Bot
from telegram.error import TelegramError

from bot.config import settings
from bot.schemas import InternalAlertRequest
from bot.state import redis_state
from salesos_shared.logging import get_logger, log_extra


logger = get_logger(__name__)


class AlertFanoutService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def dispatch(self, alert: InternalAlertRequest) -> dict:
        payload = alert.model_dump()
        try:
            await redis_state.set_json("salesos:telegram:last_alert", payload, ttl_seconds=86400)
            await redis_state.push_json("salesos:telegram:alerts", payload, max_items=25, ttl_seconds=86400)
        except Exception as exc:
            logger.warning(
                "Telegram alert cache write failed",
                extra=log_extra(service="telegram-bot", error=str(exc)),
            )

        delivered = 0
        if settings.telegram_bot_token not in {"", "replace-me"}:
            for chat_id in settings.telegram_alert_chats:
                try:
                    await self.bot.send_message(chat_id=chat_id, text=self._render(alert))
                    delivered += 1
                except TelegramError as exc:
                    logger.warning(
                        "Telegram send failed",
                        extra=log_extra(service="telegram-bot", chat_id=chat_id, error=str(exc)),
                    )

        return {"status": "accepted", "delivered": delivered}

    @staticmethod
    def _render(alert: InternalAlertRequest) -> str:
        return f"{alert.title}\nLevel: {alert.level}\n{alert.message}"
