"""Monthly season pass (DECISION-17): rules and the reward ladder; storage lives in db.Store.

A season is a calendar month ("YYYY-MM"). Pass XP is the game XP a player earns that month (already
reduced for games with bots), 100 XP per tier, 20 tiers. Everyone has the free track; the paid track
(99 Stars, once per season) adds its rewards on top. Nothing affects game balance: coins, gems, a
skin and a badge only.
"""

from __future__ import annotations

PASS_START = "2026-11"  # first season with a pass
PASS_STARS = 99
PASS_TIERS = 20
PASS_XP_PER_TIER = 100
PASS_BADGE = ("pass", "🎟")


def active(season: str) -> bool:
    return season >= PASS_START


def tier_of(xp: int) -> int:
    return min(PASS_TIERS, max(0, xp) // PASS_XP_PER_TIER)


def reward(track: str, tier: int) -> dict[str, int | str]:
    """What one tier pays: {"coins": n} / {"gems": n} / {"skin": 1} / {"badge": 1}, combined."""
    if track == "free":
        out: dict[str, int | str] = {"coins": 15}
        if tier % 5 == 0:
            out["gems"] = 1
        return out
    if tier == PASS_TIERS:
        return {"gems": 5, "badge": 1}
    if tier == 10:
        return {"skin": 1}
    return {"gems": 2} if tier % 2 == 0 else {"coins": 30}


def claimable(xp: int, premium: bool, claimed: set[str]) -> list[str]:
    """Reward ids ("f3", "p3") reached but not taken yet."""
    reached = range(1, tier_of(xp) + 1)
    ids = [f"f{n}" for n in reached]
    if premium:
        ids += [f"p{n}" for n in reached]
    return [i for i in ids if i not in claimed]


def total(ids: list[str]) -> dict[str, int]:
    """Sum of the rewards behind reward ids."""
    out = {"coins": 0, "gems": 0, "skin": 0, "badge": 0}
    for rid in ids:
        for key, value in reward("free" if rid[0] == "f" else "paid", int(rid[1:])).items():
            out[key] += int(value)
    return out
