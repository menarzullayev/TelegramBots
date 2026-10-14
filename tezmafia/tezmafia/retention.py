"""Daily bonus, daily quests and referral rewards. Pure rules; storage is in db.Store."""

from __future__ import annotations

import random
from collections.abc import Callable

from tezmafia.progress import Outcome

DAILY_BASE = 10
DAILY_STEP = 5
DAILY_MAX = 40
QUEST_COINS = 15
QUEST_XP = 10
REF_INVITER_COINS = 50
REF_NEW_COINS = 25
QUESTS_PER_DAY = 3


def daily_reward(streak: int) -> tuple[int, int]:
    """(coins, gems) for the given streak day; every 7th day adds a gem."""
    coins = min(DAILY_BASE + DAILY_STEP * (max(1, streak) - 1), DAILY_MAX)
    return coins, 1 if streak % 7 == 0 else 0


def next_streak(last_day: str, today: str, yesterday: str, streak: int) -> int | None:
    """New streak after claiming today, or None if today's bonus was already taken."""
    if last_day == today:
        return None
    return streak + 1 if last_day == yesterday else 1


# key -> (target, how much one finished game adds)
QUESTS: dict[str, tuple[int, Callable[[Outcome], int]]] = {
    "play_2": (2, lambda o: 1),
    "play_3": (3, lambda o: 1),
    "win_1": (1, lambda o: int(o.won)),
    "win_2": (2, lambda o: int(o.won)),
    "survive_1": (1, lambda o: int(o.alive)),
    "win_town": (1, lambda o: int(o.won and o.faction == "town")),
    "win_mafia": (1, lambda o: int(o.won and o.faction == "mafia")),
    "win_special": (1, lambda o: int(o.won and o.role not in {"citizen", "mafia"})),
}


def todays_quests(day: str) -> list[str]:
    """The same three quests for everyone on a given day."""
    return random.Random(f"tezmafia-{day}").sample(sorted(QUESTS), QUESTS_PER_DAY)


def quest_increments(day: str, outcome: Outcome) -> dict[str, int]:
    steps = {key: QUESTS[key][1](outcome) for key in todays_quests(day)}
    return {k: v for k, v in steps.items() if v}
