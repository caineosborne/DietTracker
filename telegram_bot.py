from __future__ import annotations

import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from diettracker.domain.meal_builder import build_meal_log
from diettracker.config import app_timezone, configure_timezone
from diettracker.domain.metrics import get_now_local
from diettracker.services.meal_estimator import MealEstimator
from diettracker.stores.meal_store import MealStore
from diettracker.stores.settings_store import SettingsStore

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def get_message_timestamp(update: Update) -> datetime:
    # Read the shared GUI setting so a location change takes effect without
    # restarting the bot process.
    configure_timezone(SettingsStore().get_timezone())
    if update.message and update.message.date:
        return update.message.date.astimezone(app_timezone())
    return get_now_local()


def is_allowed(update: Update) -> bool:
    allowed_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID")

    if not allowed_user_id:
        raise ValueError("TELEGRAM_ALLOWED_USER_ID is not set.")

    user = update.effective_user
    return user is not None and str(user.id) == allowed_user_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not is_allowed(update):
        return

    if update.message:
        await update.message.reply_text("Send me a meal description.")


async def add_meal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not is_allowed(update):
        return

    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    if not raw_text:
        return

    await update.message.reply_text("Estimating meal…")

    try:
        now = get_message_timestamp(update)
        estimate = MealEstimator().estimate(raw_text, now)
        meal = build_meal_log(
            raw_text=raw_text,
            items=estimate.items,
            timestamp=now,
            created_at=now,
            summary_notes=estimate.summary_notes,
        )
        MealStore().append(meal)

        estimated_mid = sum(item.calories_mid for item in estimate.items)
        await update.message.reply_text(
            "Meal added.\n\n"
            f"{raw_text}\n"
            f"Estimated calories: {estimated_mid}"
        )
    except Exception:
        logger.exception("Could not add meal")
        await update.message.reply_text("The meal could not be added. Check the bot logs.")


def main() -> None:
    load_dotenv()
    configure_timezone(SettingsStore().get_timezone())

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_meal))
    application.run_polling()


if __name__ == "__main__":
    main()
