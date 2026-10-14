"""Raven brand: one place for the media files the bot sends and the colors generated assets use.

Telegram does not let a bot style its UI, so the brand reaches players through images, the
profile photo, stickers, custom emoji and text. Swapping the artwork means editing MEDIA only.
"""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Contrast on RAVEN_BLACK (WCAG): ivory 15.6, gold 7.7, red_text 4.8, raven_red 3.8 (marks/large text
# only), burgundy 1.8 (surface only; ivory on burgundy 9.0). See docs/brand/raven.md.
PALETTE: dict[str, str] = {
    "raven_black": "#101116",
    "charcoal": "#1A1C23",
    "burgundy": "#721F2B",
    "raven_red": "#C83D46",
    "red_text": "#D9545C",
    "gold": "#C5A15A",
    "ivory": "#F1E9DB",
    "ash": "#9A958C",
}

# Logical moment → file under assets/. The bot only ever asks for a moment.
MEDIA: dict[str, str] = {
    "roles_dealt": "day.png",
    "night": "night.png",
    "dawn": "day.png",
    "dawn_death": "death.png",
    "win_mafia": "mafia-win.png",
    "win_town": "town-win.png",
    "win_solo": "death.png",
    "avatar": "avatar.jpg",
}

_WIN = {"mafia": "win_mafia", "town": "win_town"}


def media(moment: str) -> str:
    """File name for a moment; unknown moments are a programming error, not a missing asset."""
    return MEDIA[moment]


def win_media(winner: str | None) -> str:
    """Victory image: Mafia and town have their own; every solo role shares one."""
    if not winner:
        return media("win_town")
    return media(_WIN.get(winner, "win_solo"))


def missing_media() -> list[str]:
    return sorted({name for name in MEDIA.values() if not (ASSETS / name).is_file()})
