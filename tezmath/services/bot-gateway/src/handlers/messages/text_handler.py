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


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    chat_id = update.effective_chat.id
    text = update.message.text or ""

    await save_chat_message(
        chat_id=chat_id,
        user_id=user["telegram_id"],
        username=user.get("username"),
        full_name=user.get("full_name", ""),
        text=text,
        has_image=False,
        image_desc=None,
    )

    chat_history = await get_recent_chat_messages(chat_id, limit=CONTEXT_WINDOW + 1)
    context_history = chat_history[:-1]

    # Tarixdagi oxirgi rasmni topib, qayta yuklaymiz —
    # foydalanuvchi "3" deb javob berganda original rasm Claude'ga uzatilsin.
    image_data: bytes | None = None
    for msg in reversed(context_history):
        if msg.get("file_id"):
            try:
                file = await context.bot.get_file(msg["file_id"])
                image_data = bytes(await file.download_as_bytearray())
                logger.info("Re-fetched image file_id=%s for context", msg["file_id"])
            except Exception as e:
                logger.warning("Could not re-fetch image: %s", e)
            break

    processing_msg = await update.message.reply_text(t(lang, "processing"))

    try:
        result = await publish_solver_task(
            user_id=user["id"],
            telegram_id=user["telegram_id"],
            input_type="text",
            content=text,
            lang=lang,
            image_data=image_data,
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
        logger.error(f"Solver error for user {user['telegram_id']}: {e}")
        await processing_msg.edit_text(t(lang, "error"))
