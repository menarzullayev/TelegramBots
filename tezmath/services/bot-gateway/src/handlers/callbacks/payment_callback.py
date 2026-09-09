import logging

from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes

from config import get_settings
from middleware.auth import AuthMiddleware
from middleware.i18n import t

settings = get_settings()
logger = logging.getLogger(__name__)

MONTHLY_PRICE_STARS = 150  # Telegram Stars
MONTHLY_PRICE_UZS = 30_000


async def payment_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    # callback_data format: "pay:<method>:<period>"
    parts = query.data.split(":")
    if len(parts) != 3:
        return

    method = parts[1]  # payme | click | stars
    period = parts[2]  # monthly | yearly

    lang = user.get("language", "uz")

    if method == "stars":
        await _handle_stars_payment(update, context, user, lang, period)
    elif method in ("payme", "click"):
        await _handle_card_payment(update, context, user, lang, method, period)


async def _handle_stars_payment(update, context, user, lang, period):
    query = update.callback_query
    title = "TezMath Premium (1 oy)" if lang == "uz" else "TezMath Premium (1 мес)"
    description = (
        "Cheksiz masala yechish, tez javob, LaTeX render"
        if lang == "uz"
        else "Безлимитные задачи, быстрые ответы, LaTeX рендеринг"
    )
    prices = [LabeledPrice("Premium", MONTHLY_PRICE_STARS)]

    try:
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=title,
            description=description,
            payload=f"premium:stars:{user['id']}:{period}",
            provider_token="",  # empty for Telegram Stars
            currency="XTR",
            prices=prices,
        )
    except Exception as e:
        logger.error(f"Stars invoice error for user {user['telegram_id']}: {e}")
        await query.message.reply_text(t(lang, "error"))


async def _handle_card_payment(update, context, user, lang, method, period):
    query = update.callback_query
    # Redirect user to external payment page (Payme/Click)
    from services.payment_client import create_payment_order

    order = await create_payment_order(
        user_id=user["id"],
        method=method,
        amount=MONTHLY_PRICE_UZS,
        period=period,
    )

    if not order:
        await query.message.reply_text(t(lang, "error"))
        return

    label = "💳 To'lov sahifasi" if lang == "uz" else "💳 Страница оплаты"
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup([[InlineKeyboardButton(label, url=order["payment_url"])]])
    msg = (
        "💎 Premium olinmoqda...\n\n🔗 To'lov havolasi tayyor.\n⏱ Muddat: 15 daqiqa"
        if lang == "uz"
        else "💎 Оформление Premium...\n\n🔗 Ссылка на оплату готова.\n⏱ Действует: 15 минут"
    )
    await query.message.reply_text(msg, reply_markup=kb)


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram Stars pre-checkout confirmation."""
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram Stars payment confirmed — activate subscription."""
    allowed, user = await AuthMiddleware.process(update)
    if not allowed:
        return

    payment = update.message.successful_payment
    payload = payment.invoice_payload  # "premium:stars:<user_id>:<period>"
    lang = user.get("language", "uz")

    from database.queries import activate_premium

    await activate_premium(user["id"], months=1, method="stars", amount=payment.total_amount)

    msg = (
        "🎉 *Premium faollashtirildi!*\n\n✨ Endi siz cheksiz masala yechishingiz mumkin!"
        if lang == "uz"
        else "🎉 *Premium активирован!*\n\n✨ Теперь вы можете решать неограниченное количество задач!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    logger.info(f"Stars payment successful for user {user['telegram_id']}, payload={payload}")
