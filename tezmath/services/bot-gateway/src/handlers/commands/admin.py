import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import get_settings
from database.queries import get_admin_stats
from middleware.auth import AuthMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_id_list


async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    if not _is_admin(user["telegram_id"]):
        await update.effective_message.reply_text("⛔ Access denied.")
        return

    stats = await get_admin_stats()

    text = (
        f"🛠 *Admin Panel*\n\n"
        f"👥 Jami foydalanuvchilar: {stats['total_users']}\n"
        f"💎 Premium: {stats['premium_users']}\n"
        f"📊 Bugungi yechimlar: {stats['today_solutions']}\n"
        f"📊 Jami yechimlar: {stats['total_solutions']}\n"
        f"💰 Oylik daromad: {stats['monthly_revenue']:,} UZS\n\n"
        f"📈 Yangi foydalanuvchilar (7 kun): {stats['new_users_7d']}"
    )

    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: /broadcast <message>"""
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    if not _is_admin(user["telegram_id"]):
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    from services.notification_producer import publish_broadcast

    job_id = await publish_broadcast(message)
    await update.effective_message.reply_text(f"✅ Broadcast queued: job_id={job_id}")


async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: /ban <telegram_id>"""
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    if not _is_admin(user["telegram_id"]):
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /ban <telegram_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("❌ Invalid telegram_id")
        return

    from database.queries import ban_user

    await ban_user(target_id)
    await update.effective_message.reply_text(f"✅ User {target_id} banned.")
    logger.warning(f"Admin {user['telegram_id']} banned user {target_id}")
