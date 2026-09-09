TRANSLATIONS = {
    "uz": {
        "welcome": "👋 Assalomu alaykum! TezMath botiga xush kelibsiz!\n\n📐 Matematika masalangizni yozing yoki rasm yuboring.",
        "help": "📚 *Yordam*\n\n✏️ Matn yuboring — masala yechilib beriladi\n📷 Rasm yuboring — masala o'qilib yechilib beriladi\n\n*Buyruqlar:*\n/profile — Profilingiz\n/premium — Premium obuna\n/history — So'nggi yechimlar\n/settings — Sozlamalar",
        "limit_exceeded": "⚠️ Bugunlik bepul limitingiz tugadi ({limit} ta).\n\n💎 Premium obuna oling — cheksiz foydalaning!",
        "processing": "⏳ Masala yechilmoqda...",
        "error": "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
        "rate_remaining": "📊 Bugun qolgan: {remaining}/{limit}",
        "premium_required": "💎 Bu funksiya faqat Premium foydalanuvchilar uchun.",
        "banned": "🚫 Hisobingiz bloklangan. Murojaat: @TezMathSupport",
        "choose_language": "🌐 Tilni tanlang:",
        "settings_saved": "✅ Sozlamalar saqlandi.",
        "processing_photo": "⏳ Rasm o'qilmoqda va masala yechilmoqda...",
        "photo_too_large": "❌ Rasm juda katta (max 10MB). Kichikroq rasm yuboring.",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать в TezMath!\n\n📐 Напишите задачу или отправьте фото.",
        "help": "📚 *Помощь*\n\n✏️ Напишите задачу — получите решение\n📷 Отправьте фото — задача будет распознана\n\n*Команды:*\n/profile — Профиль\n/premium — Подписка\n/history — История\n/settings — Настройки",
        "limit_exceeded": "⚠️ Дневной лимит исчерпан ({limit} задач).\n\n💎 Оформите Premium — без ограничений!",
        "processing": "⏳ Решаю задачу...",
        "error": "❌ Произошла ошибка. Попробуйте ещё раз.",
        "rate_remaining": "📊 Осталось сегодня: {remaining}/{limit}",
        "premium_required": "💎 Эта функция только для Premium пользователей.",
        "banned": "🚫 Аккаунт заблокирован. Обратитесь: @TezMathSupport",
        "choose_language": "🌐 Выберите язык:",
        "settings_saved": "✅ Настройки сохранены.",
        "processing_photo": "⏳ Читаю фото и решаю задачу...",
        "photo_too_large": "❌ Фото слишком большое (max 10MB). Отправьте меньшее.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TRANSLATIONS else "uz"
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS["uz"].get(key, key))
    return text.format(**kwargs) if kwargs else text
