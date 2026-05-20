from telegram import Update
from telegram.ext import ContextTypes


async def noop_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer("Action acknowledged.")
