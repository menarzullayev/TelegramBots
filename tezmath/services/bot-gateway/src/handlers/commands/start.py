import logging

from telegram import Update
from telegram.ext import ContextTypes

from keyboards.inline import main_menu_keyboard
from middleware.auth import AuthMiddleware
from middleware.i18n import t

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    ref_code = context.args[0] if context.args else None

    if ref_code:
        from database.queries import apply_referral

        await apply_referral(user["id"], ref_code)

    await update.effective_message.reply_text(
        t(lang, "welcome"), reply_markup=main_menu_keyboard(lang), parse_mode="Markdown"
    )
    logger.info(f"User {user['telegram_id']} started bot")
