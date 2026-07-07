from __future__ import annotations

import logging
import os
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from meal_estimator import MealEstimator
from meal_store import MealStore
from schemas import MealLog
from meal_log_builder import meal_estimate_to_log


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def get_now_local() -> datetime:
    return datetime.now().astimezone()


def is_allowed(update: Update) -> bool:
    allowed_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID")

    if not allowed_user_id:
        raise ValueError("TELEGRAM_ALLOWED_USER_ID is not set.")

    user = update.effective_user
    return user is not None and str(user.id) == allowed_user_id


# def is_allowed(update: Update) -> bool:
#     user = update.effective_user
#     if user:
#         print("TELEGRAM USER ID:", user.id)
#         print("TELEGRAM USERNAME:", user.username)
#     return True

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_allowed(update):
        return

    if update.message:
        await update.message.reply_text(
            "Send me a meal description and I will add it to your tracker."
        )


async def add_meal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not is_allowed(update):
        return

    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()



    if not raw_text:
        return

    await update.message.reply_text("Estimating meal…")

    try:
        now = get_now_local()

        estimate = MealEstimator().estimate(raw_text, now)

        meal = meal_estimate_to_log(
            raw_text=raw_text,
            estimate=estimate,
            timestamp=now,
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

        await update.message.reply_text(
            "The meal could not be added. Check the bot logs."
        )


def main() -> None:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            add_meal,
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()