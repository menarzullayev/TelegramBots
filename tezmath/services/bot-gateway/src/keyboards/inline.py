from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    buttons = {
        "uz": [
            [InlineKeyboardButton("📐 Masala yechish", callback_data="menu:solve")],
            [
                InlineKeyboardButton("👤 Profil", callback_data="menu:profile"),
                InlineKeyboardButton("💎 Premium", callback_data="menu:premium"),
            ],
            [
                InlineKeyboardButton("📜 Tarix", callback_data="menu:history"),
                InlineKeyboardButton("⚙️ Sozlamalar", callback_data="menu:settings"),
            ],
        ],
        "ru": [
            [InlineKeyboardButton("📐 Решить задачу", callback_data="menu:solve")],
            [
                InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
                InlineKeyboardButton("💎 Premium", callback_data="menu:premium"),
            ],
            [
                InlineKeyboardButton("📜 История", callback_data="menu:history"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings"),
            ],
        ],
    }
    return InlineKeyboardMarkup(buttons.get(lang, buttons["uz"]))


def premium_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 Payme", callback_data="pay:payme:monthly")],
            [InlineKeyboardButton("💳 Click", callback_data="pay:click:monthly")],
            [InlineKeyboardButton("⭐ Telegram Stars", callback_data="pay:stars:monthly")],
            [InlineKeyboardButton("🔙 Orqaga" if lang == "uz" else "🔙 Назад", callback_data="menu:main")],
        ]
    )


def rating_keyboard(solution_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⭐", callback_data=f"rate:{solution_id}:1"),
                InlineKeyboardButton("⭐⭐", callback_data=f"rate:{solution_id}:2"),
                InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate:{solution_id}:3"),
                InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate:{solution_id}:4"),
                InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate:{solution_id}:5"),
            ]
        ]
    )


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇺🇿 O'zbek", callback_data="menu:lang:uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="menu:lang:ru"),
            ]
        ]
    )
