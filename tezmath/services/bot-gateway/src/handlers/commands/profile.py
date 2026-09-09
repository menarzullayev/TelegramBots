import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import get_settings
from database.queries import get_user_stats
from middleware.auth import AuthMiddleware
from middleware.rate_limit import RateLimiter

settings = get_settings()
logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(settings.redis_url)


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    is_premium = user.get("is_premium", False)

    stats = await get_user_stats(user["id"])
    _, remaining = await rate_limiter.is_allowed(user["telegram_id"], is_premium)

    if lang == "uz":
        text = (
            f"👤 *Profilingiz*\n\n"
            f"🆔 ID: `{user['telegram_id']}`\n"
            f"👤 Ism: {user.get('full_name', '—')}\n"
            f"💎 Tur: {'Premium ✨' if is_premium else 'Bepul'}\n\n"
            f"📊 *Statistika:*\n"
            f"✅ Jami yechimlar: {stats['total_solutions']}\n"
            f"⭐ O'rtacha reyting: {stats['avg_rating']:.1f}\n"
            f"📅 Bugun qolgan: {remaining}/{settings.free_daily_limit}\n\n"
            f"📅 Ro'yxatdan o'tgan: {stats['joined_at']}"
        )
    else:
        text = (
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: `{user['telegram_id']}`\n"
            f"👤 Имя: {user.get('full_name', '—')}\n"
            f"💎 Тип: {'Premium ✨' if is_premium else 'Бесплатный'}\n\n"
            f"📊 *Статистика:*\n"
            f"✅ Всего решений: {stats['total_solutions']}\n"
            f"⭐ Средний рейтинг: {stats['avg_rating']:.1f}\n"
            f"📅 Осталось сегодня: {remaining}/{settings.free_daily_limit}\n\n"
            f"📅 Дата регистрации: {stats['joined_at']}"
        )

    await update.effective_message.reply_text(text, parse_mode="Markdown")
