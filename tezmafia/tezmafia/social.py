"""Clans and the weekly tournament: rules and constants (storage is in db.Store)."""

from __future__ import annotations

import re
import time

CLAN_COST = 100
CLAN_MAX = 30
TOUR_GEMS = (5, 3, 2)
TOUR_WIN_POINTS = 3
TOUR_GAME_POINTS = 1
FAIR_AFK_PENALTY = 15
FAIR_GAME_BONUS = 3
_NAME = re.compile(r"^[^\W_](?:[\w ]{1,18})[^\W_]$")


def clean_clan_name(raw: str) -> str | None:
    """3-20 letters, digits or inner spaces (any script); None if invalid."""
    name = " ".join(raw.split())
    return name if _NAME.match(name) else None


def week_key(ts: float | None = None) -> str:
    """ISO week, e.g. 2026-W42 (weeks start on Monday)."""
    return time.strftime("%G-W%V", time.localtime(ts if ts is not None else time.time()))


def points(won: bool) -> int:
    return TOUR_GAME_POINTS + (TOUR_WIN_POINTS if won else 0)
