import logging

from telegram import Update
from telegram.ext import ContextTypes

from keyboards.inline import language_keyboard
from middleware.auth import AuthMiddleware

logger = logging.getLogger(__name__)


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    msg = "⚙️ *Sozlamalar*\n\nTilni tanlang:" if lang == "uz" else "⚙️ *Настройки*\n\nВыберите язык:"
    await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=language_keyboard())
