from telegram import Update

from bot.config import settings


def user_allowed(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    allowed = settings.telegram_allowed_users
    return not allowed or user.id in allowed
