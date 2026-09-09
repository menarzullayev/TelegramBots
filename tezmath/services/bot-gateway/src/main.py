import asyncio
import logging

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from config import get_settings
from handlers.callbacks.menu_callback import menu_callback_handler
from handlers.callbacks.payment_callback import (
    payment_callback_handler,
    precheckout_handler,
    successful_payment_handler,
)
from handlers.callbacks.rating_callback import rating_callback_handler
from handlers.commands.admin import admin_handler
from handlers.commands.help import help_handler
from handlers.commands.history import history_handler
from handlers.commands.premium import premium_handler
from handlers.commands.profile import profile_handler
from handlers.commands.settings import settings_handler
from handlers.commands.start import start_handler
from handlers.messages.photo_handler import photo_message_handler
from handlers.messages.text_handler import text_message_handler
from middleware.logger import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)


def build_application():
    app = ApplicationBuilder().token(settings.bot_token).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("profile", profile_handler))
    app.add_handler(CommandHandler("premium", premium_handler))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("admin", admin_handler))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))
    app.add_handler(MessageHandler(filters.Document.PDF, photo_message_handler))

    # Callbacks
    app.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^menu:"))
    app.add_handler(CallbackQueryHandler(payment_callback_handler, pattern="^pay:"))
    app.add_handler(CallbackQueryHandler(rating_callback_handler, pattern="^rate:"))

    # Telegram Stars payments
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    return app


def main():
    setup_logging(settings.log_level)
    logger.info(f"Starting TezMathRobot [{settings.environment}]")

    app = build_application()

    if settings.environment == "production":

        async def run_webhook():
            await app.bot.set_webhook(url=f"{settings.webhook_url}/webhook", secret_token=settings.webhook_secret)
            logger.info("Webhook mode aktiv")
            async with app:
                await app.start()
                await asyncio.Event().wait()

        asyncio.run(run_webhook())
    else:
        logger.info("Polling mode aktiv")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
