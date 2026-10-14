"""Clans and the weekly tournament: rules and constants (storage is in db.Store)."""

from __future__ import annotations

import re
import time

CLAN_COST = 100
CLAN_MAX = 30
TOUR_GEMS = (5, 3, 2)
TOUR_WIN_POINTS = 3
TOUR_GAME_POINTS = 1
FOUNDER_COINS = 200
FOUNDER_GEMS = 2
FOUNDER_MAX_GROUPS = 5  # one admin is rewarded for at most this many groups
FOUNDER_MIN_PLAYERS = 5
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


def reward_tier(people: int, seats: int) -> str:
    """DECISION-17: how much a game with bots pays its people (see Store.record_game)."""
    if people == seats or people >= 5:
        return "full"
    return "half" if people >= 3 else "xp"


def points(won: bool) -> int:
    return TOUR_GAME_POINTS + (TOUR_WIN_POINTS if won else 0)
