import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.queries import get_solution_history
from keyboards.inline import rating_keyboard
from middleware.auth import AuthMiddleware

logger = logging.getLogger(__name__)

PAGE_SIZE = 5


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    solutions = await get_solution_history(user["id"], limit=PAGE_SIZE)

    if not solutions:
        msg = "📜 Sizda hali yechimlar yo'q." if lang == "uz" else "📜 У вас ещё нет решений."
        await update.effective_message.reply_text(msg)
        return

    header = "📜 *So'nggi yechimlar:*\n\n" if lang == "uz" else "📜 *Последние решения:*\n\n"
    await update.effective_message.reply_text(header, parse_mode="Markdown")

    for sol in solutions:
        preview = sol["input_text"][:80] + "..." if len(sol["input_text"]) > 80 else sol["input_text"]
        created = sol["created_at"].strftime("%d.%m.%Y %H:%M")
        caption = f"🔢 `{preview}`\n📅 {created}"

        await update.effective_message.reply_text(
            caption, reply_markup=rating_keyboard(sol["id"]), parse_mode="Markdown"
        )
