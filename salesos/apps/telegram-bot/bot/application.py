from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.config import settings
from bot.handlers.callbacks import noop_callback
from bot.handlers.commands import (
    start_command,
    hot_leads_command,
    scrape_command,
    stats_command,
    status_command,
)


def build_application() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("scrape", scrape_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("hot_leads", hot_leads_command))
    application.add_handler(CallbackQueryHandler(noop_callback))
    return application
