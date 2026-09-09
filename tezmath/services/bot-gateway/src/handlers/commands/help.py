import logging

from telegram import Update
from telegram.ext import ContextTypes

from middleware.auth import AuthMiddleware
from middleware.i18n import t

logger = logging.getLogger(__name__)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    await update.effective_message.reply_text(t(lang, "help"), parse_mode="Markdown")
