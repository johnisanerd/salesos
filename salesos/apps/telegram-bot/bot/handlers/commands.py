import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import settings
from bot.services.api_client import APIClientService
from bot.services.whitelist import user_allowed
from bot.state import redis_state


async def start_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_allowed(update):
        return
    await update.message.reply_text(
        "SalesOS bot is online.\nUse /status to check the latest pipeline summary."
    )


async def status_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_allowed(update):
        return
    try:
        last_scrape = await redis_state.get_json("salesos:pipeline:last_scrape")
    except Exception:
        last_scrape = None
    summary = "No scrape run has been recorded yet."
    if last_scrape:
        summary = last_scrape["summary"]
    await update.message.reply_text(f"SalesOS bot is online.\n{summary}")


async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_allowed(update):
        return
    args = context.args or []
    query = " ".join(args).strip() if args else settings.default_scrape_query
    location = settings.default_scrape_location
    max_results = settings.default_scrape_max_results
    try:
        await redis_state.set_text(
            f"telegram:last_command:{update.effective_chat.id}",
            f"scrape:{query}",
            ttl_seconds=3600,
        )
    except Exception:
        pass
    result = await APIClientService().trigger_scrape(
        query=query,
        location=location,
        max_results=max_results,
        request_id=str(uuid.uuid4()),
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open API docs", url="http://localhost:8000/docs")]],
    )
    if result.get("status") == "failed":
        await update.message.reply_text(
            f"Scrape trigger failed: {result['error']}",
            reply_markup=keyboard,
        )
        return
    await update.message.reply_text(
        (
            f"Pipeline triggered.\n"
            f"Query: {query}\n"
            f"Inserted: {result['inserted']}\n"
            f"Deduplicated: {result['deduplicated']}\n"
            f"Reused existing: {result.get('reused_existing', 0)}\n"
            f"Analyzed: {result.get('analyzed', 0)}\n"
            f"Outreach generated: {result.get('outreach_generated', 0)}\n"
            f"Skipped cooldown: {result.get('skipped_due_to_cooldown', 0)}\n"
            f"Invalid: {result['invalid']}"
        ),
        reply_markup=keyboard,
    )


async def stats_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_allowed(update):
        return
    try:
        last_scrape = await redis_state.get_json("salesos:pipeline:last_scrape")
    except Exception:
        last_scrape = None
    if not last_scrape:
        await update.message.reply_text("No scrape stats are available yet.")
        return
    await update.message.reply_text(
        (
            f"Latest scrape stats\n"
            f"Received: {last_scrape['total_received']}\n"
            f"Inserted: {last_scrape['inserted']}\n"
            f"Deduplicated: {last_scrape['deduplicated']}\n"
            f"Reused existing: {last_scrape.get('reused_existing', 0)}\n"
            f"Analyzed: {last_scrape.get('analyzed', 0)}\n"
            f"Outreach generated: {last_scrape.get('outreach_generated', 0)}\n"
            f"Skipped cooldown: {last_scrape.get('skipped_due_to_cooldown', 0)}\n"
            f"Invalid: {last_scrape['invalid']}"
        )
    )


async def hot_leads_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_allowed(update):
        return
    try:
        recent_alert = await redis_state.get_json("salesos:telegram:last_alert")
    except Exception:
        recent_alert = None
    if not recent_alert:
        await update.message.reply_text("No alerts have been recorded yet.")
        return
    await update.message.reply_text(f"{recent_alert['title']}\n{recent_alert['message']}")
