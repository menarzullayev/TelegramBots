import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import get_settings
from keyboards.inline import premium_keyboard
from middleware.auth import AuthMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)

PREMIUM_PRICE_UZS = 30_000


async def premium_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    lang = user.get("language", "uz")
    is_premium = user.get("is_premium", False)

    if is_premium:
        sub_end = user.get("subscription_end", "—")
        if lang == "uz":
            text = f"✨ Siz allaqachon *Premium* foydalanuvchisiz!\n\n📅 Muddati: {sub_end}"
        else:
            text = f"✨ Вы уже *Premium* пользователь!\n\n📅 Истекает: {sub_end}"
        await update.effective_message.reply_text(text, parse_mode="Markdown")
        return

    if lang == "uz":
        text = (
            f"💎 *TezMath Premium*\n\n"
            f"✅ Cheksiz masalalar yechish\n"
            f"✅ Tezkor javob (1 soniya)\n"
            f"✅ Rasm orqali masala yuborish\n"
            f"✅ Yechim tarixi (1 yillik)\n"
            f"✅ LaTeX render qilingan yechimlar\n\n"
            f"💰 Narx: *{PREMIUM_PRICE_UZS:,} UZS/oy*\n\n"
            f"To'lov usulini tanlang:"
        )
    else:
        text = (
            f"💎 *TezMath Premium*\n\n"
            f"✅ Неограниченное решение задач\n"
            f"✅ Быстрый ответ (1 секунда)\n"
            f"✅ Отправка фото задач\n"
            f"✅ История решений (1 год)\n"
            f"✅ Решения с LaTeX рендерингом\n\n"
            f"💰 Цена: *{PREMIUM_PRICE_UZS:,} UZS/мес*\n\n"
            f"Выберите способ оплаты:"
        )

    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=premium_keyboard(lang))
