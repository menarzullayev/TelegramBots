import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.queries import update_user_language
from keyboards.inline import language_keyboard, main_menu_keyboard
from middleware.auth import AuthMiddleware
from middleware.i18n import t

logger = logging.getLogger(__name__)


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    action = query.data.split(":", 1)[1]  # "menu:<action>"

    if action == "main":
        await query.edit_message_text(t(lang, "welcome"), reply_markup=main_menu_keyboard(lang), parse_mode="Markdown")

    elif action == "solve":
        msg = "✏️ Masalangizni yozing yoki rasm yuboring:" if lang == "uz" else "✏️ Напишите задачу или отправьте фото:"
        await query.edit_message_text(msg)

    elif action == "profile":
        from handlers.commands.profile import profile_handler

        await profile_handler(update, context)

    elif action == "premium":
        from handlers.commands.premium import premium_handler

        await premium_handler(update, context)

    elif action == "history":
        from handlers.commands.history import history_handler

        await history_handler(update, context)

    elif action == "settings":
        msg = "⚙️ *Sozlamalar*\n\nTilni tanlang:" if lang == "uz" else "⚙️ *Настройки*\n\nВыберите язык:"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=language_keyboard())

    elif action.startswith("lang:"):
        new_lang = action.split(":")[1]
        if new_lang in ("uz", "ru"):
            await update_user_language(user["id"], new_lang)
            await query.edit_message_text(t(new_lang, "settings_saved"), reply_markup=main_menu_keyboard(new_lang))
