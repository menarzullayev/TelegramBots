import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.queries import save_solution_rating
from middleware.auth import AuthMiddleware

logger = logging.getLogger(__name__)


async def rating_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        await query.answer()
        return

    # callback_data format: "rate:<solution_id>:<stars>"
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer()
        return

    solution_id = int(parts[1])
    stars = int(parts[2])

    await save_solution_rating(solution_id, user["id"], stars)

    lang = user.get("language", "uz")
    msg = f"⭐ {'Rahmat!' if lang == 'uz' else 'Спасибо!'} ({stars}/5)"
    await query.answer(msg)

    # Remove rating keyboard after rating
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
