"""Raven brand: one place for the media files the bot sends and the colors generated assets use.

Telegram does not let a bot style its UI, so the brand reaches players through images, the
profile photo, stickers, custom emoji and text. Swapping the artwork means editing MEDIA only.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from tezmafia.roles import Role

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
    "roles_dealt": "raven/scenes/roles-dealt.jpg",
    "night": "raven/scenes/night.jpg",
    "dawn": "raven/scenes/dawn.jpg",
    "dawn_death": "raven/scenes/dawn-death.jpg",
    "trial": "raven/scenes/trial.jpg",
    "verdict_confirm": "raven/scenes/verdict-confirm.jpg",
    "verdict_sealed": "raven/scenes/verdict-sealed.jpg",
    "win_mafia": "raven/scenes/win-mafia.jpg",
    "win_town": "raven/scenes/win-town.jpg",
    "win_maniac": "raven/scenes/win-maniac.jpg",
    "win_suicide": "raven/scenes/win-suicide.jpg",
    "win_arsonist": "raven/scenes/win-arsonist.jpg",
    "win_snitch": "raven/scenes/win-snitch.jpg",
    "win_mage": "raven/scenes/win-mage.jpg",
    "win_crook": "raven/scenes/win-crook.jpg",
    "win_solo": "raven/scenes/dawn-death.jpg",
    "menu_start": "raven/menu/h01-start.jpg",
    "menu_help": "raven/menu/h02-help.jpg",
    "menu_shop": "raven/menu/h03-shop.jpg",
    "menu_profile": "raven/menu/h04-profile.jpg",
    "menu_top": "raven/menu/h05-top.jpg",
    "avatar": "raven/avatar.jpg",
}

# Telegram limit for photo captions, counted on the text after HTML entities are parsed.
CAPTION_LIMIT = 1024

_TAG = re.compile(r"<[^>]+>")


def media(moment: str) -> str:
    """File name for a moment; unknown moments are a programming error, not a missing asset."""
    return MEDIA[moment]


def win_media(winner: str | None) -> str:
    """Victory image: every winner with its own scene gets it; anything else shares win_solo."""
    if not winner:
        return media("win_town")
    if winner == "draw":
        return media("night")  # an empty town, not anybody's victory
    return MEDIA.get(f"win_{winner}", MEDIA["win_solo"])


def role_card(role: str, skin: str = "") -> str | None:
    """Portrait card for a role id (in the player's skin when that file exists), or None for an unknown id."""
    if role not in {r.value for r in Role}:
        return None
    if skin and (ASSETS / "raven" / "skins" / skin / f"{role}.jpg").is_file():
        return f"raven/skins/{skin}/{role}.jpg"
    return f"raven/roles/{role}.jpg"


def caption_fits(html_text: str) -> bool:
    """True when the HTML text stays within the photo caption limit once tags are stripped."""
    return len(html.unescape(_TAG.sub("", html_text))) <= CAPTION_LIMIT


def missing_media() -> list[str]:
    names = set(MEDIA.values()) | {f"raven/roles/{r.value}.jpg" for r in Role}
    return sorted(name for name in names if not (ASSETS / name).is_file())
