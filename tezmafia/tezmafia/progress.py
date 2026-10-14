"""Experience, levels and achievements. Pure functions; storage lives in db.Store."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

XP_PLAY = 10
XP_WIN = 20
XP_SURVIVE = 5
XP_PER_LEVEL_STEP = 50
SOLO_WINNERS = {"maniac", "suicide", "arsonist", "snitch", "mage", "crook"}


@dataclass(frozen=True)
class Outcome:
    """One player's result in a finished game, plus their totals after it was recorded."""

    role: str
    faction: str
    winner: str
    won: bool
    alive: bool
    games: int
    wins: int
    xp: int


def xp_for(won: bool, alive: bool) -> int:
    return XP_PLAY + (XP_WIN if won else 0) + (XP_SURVIVE if alive else 0)


def level_of(xp: int) -> int:
    """Level 1 at 0 XP; each next level needs a growing amount (50, 200, 450, 800 ... XP)."""
    return int(math.sqrt(max(0, xp) / XP_PER_LEVEL_STEP)) + 1


ACHIEVEMENTS: dict[str, Callable[[Outcome], bool]] = {
    "first_game": lambda o: o.games >= 1,
    "games_10": lambda o: o.games >= 10,
    "games_50": lambda o: o.games >= 50,
    "games_100": lambda o: o.games >= 100,
    "first_win": lambda o: o.wins >= 1,
    "wins_10": lambda o: o.wins >= 10,
    "wins_50": lambda o: o.wins >= 50,
    "survivor": lambda o: o.won and o.alive,
    "win_mafia": lambda o: o.won and o.faction == "mafia",
    "win_don": lambda o: o.won and o.role == "don",
    "win_detective": lambda o: o.won and o.role == "detective",
    "win_doctor": lambda o: o.won and o.role == "doctor",
    "win_solo": lambda o: o.won and o.winner in SOLO_WINNERS,
    "level_5": lambda o: level_of(o.xp) >= 5,
    "level_10": lambda o: level_of(o.xp) >= 10,
}


def earned(outcome: Outcome) -> set[str]:
    return {key for key, rule in ACHIEVEMENTS.items() if rule(outcome)}
