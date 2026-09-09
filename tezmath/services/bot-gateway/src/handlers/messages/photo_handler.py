import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import get_settings
from database.queries import get_recent_chat_messages, save_chat_message
from keyboards.inline import rating_keyboard
from middleware.auth import AuthMiddleware
from middleware.i18n import t
from middleware.rate_limit import RateLimiter
from services.queue_producer import CONTEXT_WINDOW, publish_solver_task
from services.render_solution import render_solution_to_png

settings = get_settings()
logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(settings.redis_url)

MAX_PHOTO_SIZE_MB = 10


async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    is_premium = user.get("is_premium", False)
    allowed_req, remaining = await rate_limiter.is_allowed(user["telegram_id"], is_premium)

    if not allowed_req:
        await update.message.reply_text(
            t(lang, "limit_exceeded", limit=settings.free_daily_limit),
            reply_markup=__import__("keyboards.inline", fromlist=["premium_keyboard"]).premium_keyboard(lang),
        )
        return

    photo = update.message.photo[-1]  # highest resolution
    if photo.file_size and photo.file_size > MAX_PHOTO_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(t(lang, "photo_too_large"))
        return

    caption = update.message.caption or ""
    chat_id = update.effective_chat.id

    # Rasmni DB ga saqlash: caption yoki default tavsif
    image_desc = caption or ("matematik masala rasmi" if lang == "uz" else "изображение с задачей")
    await save_chat_message(
        chat_id=chat_id,
        user_id=user["telegram_id"],
        username=user.get("username"),
        full_name=user.get("full_name", ""),
        text=caption or None,
        has_image=True,
        image_desc=image_desc,
        file_id=photo.file_id,
    )

    chat_history = await get_recent_chat_messages(chat_id, limit=CONTEXT_WINDOW + 1)
    # exclude the current message (last) — passed as image_data + content
    context_history = chat_history[:-1]

    processing_msg = await update.message.reply_text(t(lang, "processing_photo"))

    try:
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        result = await publish_solver_task(
            user_id=user["id"],
            telegram_id=user["telegram_id"],
            input_type="photo",
            content=caption,
            image_data=bytes(file_bytes),
            lang=lang,
            chat_history=context_history,
        )

        await processing_msg.delete()

        png = render_solution_to_png(result["solution_text"])
        if png:
            import io

            buf = io.BytesIO(png)
            buf.name = "solution.png"
            await update.message.reply_photo(
                buf,
                reply_markup=rating_keyboard(result["solution_id"]),
            )
        else:
            await update.message.reply_text(
                result["solution_text"],
                reply_markup=rating_keyboard(result["solution_id"]),
            )

        if not is_premium:
            await update.message.reply_text(
                t(lang, "rate_remaining", remaining=remaining - 1, limit=settings.free_daily_limit)
            )

    except Exception as e:
        logger.error(f"Photo solver error for user {user['telegram_id']}: {e}")
        await processing_msg.edit_text(t(lang, "error"))
