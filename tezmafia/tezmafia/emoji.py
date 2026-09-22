"""Custom emoji — VectorGuard slot map (PC, curated animated IDs)."""
from __future__ import annotations

import html

# slot → (custom_emoji_id, fallback). Source: /home/nsn/Telegram/vectorguard/.../emoji.py
SLOTS: dict[str, tuple[str, str]] = {
    "check": ("5260726538302660868", "✅"),
    "cross": ("5258226313285607065", "❌"),
    "hourglass": ("5258419835922030550", "⏳"),
    "door": ("5258084656674250503", "🚪"),
    "group": ("5258513401784573443", "👥"),
    "robot": ("5258093637450866522", "🤖"),
    "pin": ("5258461531464539536", "📌"),
    "bolt": ("5258152182150077732", "⚡"),
    "lock": ("5393302369024882368", "🔒"),
    "shield": ("5895483165182529286", "🛡"),
    "book": ("5255823399342587887", "📖"),
    "wave": ("5247133031235329609", "👋"),
    "timer": ("5947290074319162163", "⏱"),
    "party": ("4945206876255028064", "🎉"),
    "star": ("5458799228719472718", "🌟"),
    "help": ("5220108512893344933", "🆘"),
    "cancel": ("5872829476143894491", "🚫"),
    "warning": ("5881702736843511327", "⚠️"),
    "mute": ("5258267368877989660", "🔇"),
    "info": ("5258503720928288433", "ℹ️"),
    "search": ("5429571366384842791", "🔎"),
    "night": ("5258419835922030550", "🌙"),
    "day": ("5458799228719472718", "☀️"),
    "death": ("5258226313285607065", "💀"),
    "mafia": ("5393302369024882368", "🖤"),
    "town": ("5895483165182529286", "🏛"),
    "vote": ("5258152182150077732", "⚖️"),
}


def ce(name: str) -> str:
    cid, fallback = SLOTS.get(name, ("", name))
    if not cid:
        return html.escape(fallback)
    return f'<tg-emoji emoji-id="{html.escape(cid, quote=True)}">{html.escape(fallback)}</tg-emoji>'


def icon(name: str) -> str | None:
    entry = SLOTS.get(name)
    return entry[0] if entry else None


# Private-chat message effects (Bot API 7.0+). Group chats ignore them.
FX = {
    "fire": "5104841245755180586",
    "confetti": "5046589136895476101",
    "heart": "5159385139981059251",
    "thumbsup": "5107584321108051014",
}
