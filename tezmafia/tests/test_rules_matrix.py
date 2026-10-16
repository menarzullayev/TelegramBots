"""Rules matrix: explicit expected outcomes for every night-action interaction, the day effects and
every win condition, built from minimal deterministic games (no randomness, no database).

The expectations are written from the player-facing texts (`role.*` in locales/en.json, the channel
posts 12-18, `/help`) and checked against the engine. Where the engine does something the texts do not
say (or contradict) the row still asserts the CURRENT engine behaviour and carries the `discrepancy`
marker, with an id `D<n>` that is explained in docs/RULES-VERIFICATION.md. Changing such a behaviour on
purpose means changing that row and that document together.

Seats are 1-based, row indexes are 0-based: player `i` sits on seat `i + 1`.
"""

from __future__ import annotations

import itertools

import pytest

from tezmafia.engine import (
    Game,
    Phase,
    Player,
    Winner,
    begin_lynch,
    begin_night,
    begin_voting,
    end_if_stalemate,
    kick,
    new_game,
    peek_votes,
    resolve_lynch,
    resolve_night,
    resolve_votes,
    set_lynch_vote,
    set_night_action,
    set_vote,
    win_check,
)
from tezmafia.roles import NIGHT_ROLES, ROLE_FACTION, SPECIALS, Faction, Role, bag_for, chaos_bag, without

D = pytest.mark.discrepancy


def disc(code: str, *args, **kw):
    """pytest.param carrying the discrepancy marker; the id is prefixed with the discrepancy code."""
    pid = kw.pop("id", None) or "-".join(str(a) for a in args)
    return pytest.param(*args, id=f"{code}:{pid}", marks=D)


# --------------------------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------------------------

def build(
    spec: list,
    *,
    night_no: int = 2,
    pad: int = 6,
    resolve: str = "majority",
    reveal: bool = True,
    marks: tuple[int, ...] = (),
) -> Game:
    """Night `night_no` with the given players (role name or (role, {attribute: value})) + `pad` citizens.

    The citizens keep the table from ending in a mafia win; the Detective may shoot from night 2 on.
    """
    g = new_game(1, 10, mafia_resolve=resolve, reveal_on_death=reveal)
    items = [s if isinstance(s, tuple) else (s, {}) for s in spec] + [("citizen", {})] * pad
    for i, (role, attrs) in enumerate(items):
        p = Player(
            user_id=(i + 1) * 10, first_name=f"P{i + 1}", username=None, seat=i + 1, role=role,
            faction=ROLE_FACTION[Role(role)].value, dm_ok=True,
        )
        for key, value in attrs.items():
            setattr(p, key, value)
        g.players.append(p)
    g.night_no = night_no - 1
    begin_night(g, 0, 60)
    g.arson_marks = [m + 1 for m in marks]
    return g


def act(g: Game, actor: int, target: int, kind: str = "") -> tuple[bool, str]:
    return set_night_action(g, g.players[actor].user_id, target + 1, kind)


def night(g: Game, *acts: tuple) -> dict:
    """Submit (actor, target[, kind]) actions - each must be accepted - and resolve the night."""
    for a in acts:
        actor, target, *kind = a
        ok, why = act(g, actor, target, *(kind or [""]))
        assert ok, f"{a} refused: {why}"
    return resolve_night(g)


def alive(g: Game, *idx: int) -> tuple[bool, ...]:
    return tuple(g.players[i].alive for i in idx)


def day_votes(g: Game, votes: dict[int, int | None]) -> None:
    """Move a resolved night to the voting phase and cast {voter: target} (indexes)."""
    g.phase = Phase.DAY
    begin_voting(g, 0, 60)
    for voter, target in votes.items():
        if target is None:
            continue
        ok, why = set_vote(g, g.players[voter].user_id, target + 1)
        assert ok, f"vote {voter}->{target} refused: {why}"


# --------------------------------------------------------------------------------------------
# 1. Lethal sources x victim kinds x (no protection | Doctor protecting the victim)
#    attacker is player 0, victim player 1, the Doctor player 2
# --------------------------------------------------------------------------------------------

SOURCES = ["mafia", "don", "maniac", "killer", "shoot", "gun", "ignite"]
ATTACKER = {
    "mafia": "mafia", "don": "don", "maniac": "maniac", "killer": "killer", "shoot": "detective",
    "gun": ("citizen", {"shop_gun": True}), "ignite": "arsonist",
}
# Do Doctor's protection rules apply? Mafia/Don/Maniac/Detective bullet/pistol yes; Executioner and fire no.
RESPECTS_PROTECTION = {"mafia", "don", "maniac", "shoot", "gun"}

VICTIMS = {
    "citizen": "citizen",
    "sergeant": "sergeant",
    "mayor": "mayor",
    "suicide": "suicide",
    "kamikaze": "kamikaze",
    "lucky": "lucky",
    "lucky_spent": ("lucky", {"lucky_used": True}),
    "mage": "mage",
    "werewolf": "werewolf",
    "hobo_home": "hobo",
    "hobo_away": "hobo",
    "doctor": "doctor",
    "detective": "detective",
    "lawyer": "lawyer",
    "shield": ("citizen", {"shop_shield": True}),
    "killer_shield": ("citizen", {"shop_killer_shield": True}),
    "mask": ("citizen", {"shop_mask": True}),
    "fake_id": ("citizen", {"shop_fake_id": True}),
    "vote_shield": ("citizen", {"shop_vote_shield": True}),
}

# Codes:  D victim dies | L victim lives untouched | S victim lives, a one-use item was spent
#         X victim lives, the attacker dies instead | B both die | C victim lives and joins the Mafia
#         H victim lives (hobo away from home: empty house) | P victim lives because the Doctor saved them
#         - combination cannot be played (the engine refuses the action)
#                    mafia don maniac killer shoot gun ignite
UNPROTECTED = {
    "citizen":       "D D D D D D D",
    "sergeant":      "D D D D D D D",
    "mayor":         "D D D D D D D",
    "suicide":       "D D D D D D D",
    "kamikaze":      "B B B B B B B",
    "lucky":         "S S S S S S S",
    "lucky_spent":   "D D D D D D D",
    "mage":          "X X X X X X X",
    "werewolf":      "C C D C D D D",
    "hobo_home":     "D D D D D D D",
    "hobo_away":     "H H H H H H H",
    "doctor":        "D D D D D D D",
    "detective":     "D D D X - D D",
    "lawyer":        "- - D - D D D",
    "shield":        "S S S S S S S",
    "killer_shield": "D D D S D D D",
    "mask":          "D D D D D D D",
    "fake_id":       "D D D D D D D",
    "vote_shield":   "D D D D D D D",
}
# Same rows with the Doctor protecting the victim: only the sources that respect protection change.
PROTECTED_SKIP = {"doctor"}  # the protector would be the second Doctor, and only the first Doctor acts


def _protected(victim: str, source: str, code: str) -> str:
    if code == "-" or source not in RESPECTS_PROTECTION:
        return code
    return "P"


# Rows whose current engine behaviour is a documented discrepancy (code, text, ...).
LETHAL_DISCREPANCY = {
    ("hobo_away", "killer"): "D14",   # "No protection stops the Executioner" - an empty house does
    ("hobo_away", "ignite"): "D4",
    ("hobo_away", "mafia"): "D4",
    ("hobo_away", "don"): "D4",
    ("hobo_away", "maniac"): "D4",
    ("hobo_away", "shoot"): "D4",
    ("hobo_away", "gun"): "D4",
    ("shield", "killer"): "D20",      # "No protection stops the Executioner" vs. the shop's Night shield
    ("lucky", "killer"): "D20",
}


def _lethal_cases():
    for victim in VICTIMS:
        codes = UNPROTECTED[victim].split()
        for source, code in zip(SOURCES, codes, strict=True):
            if code == "-":
                continue
            for protect in (False, True):
                if protect and victim in PROTECTED_SKIP:
                    continue
                expected = _protected(victim, source, code) if protect else code
                pid = f"{source}>{victim}{'+doctor' if protect else ''}"
                dcode = LETHAL_DISCREPANCY.get((victim, source)) if not protect or source not in RESPECTS_PROTECTION else None
                if dcode:
                    yield pytest.param(source, victim, protect, expected, id=f"{dcode}:{pid}", marks=D)
                else:
                    yield pytest.param(source, victim, protect, expected, id=pid)


@pytest.mark.parametrize(("source", "victim", "protect", "expected"), list(_lethal_cases()))
def test_lethal_matrix(source: str, victim: str, protect: bool, expected: str) -> None:
    spec: list = [ATTACKER[source], VICTIMS[victim], "doctor"]
    marks = (1,) if source == "ignite" else ()
    g = build(spec, marks=marks)
    acts: list[tuple] = []
    if source == "ignite":
        acts.append((0, 0))
    else:
        acts.append((0, 1, "shoot") if source == "shoot" else (0, 1))
    if victim == "hobo_away":
        acts.append((1, 3))
    if protect:
        acts.append((2, 1))
    out = night(g, *acts)
    atk, vic = g.players[0], g.players[1]
    if expected == "D":
        assert not vic.alive and atk.alive
        assert vic.seat in g.night_deaths
    elif expected == "L":
        assert vic.alive and atk.alive
    elif expected == "S":
        assert vic.alive and atk.alive
        assert vic.lucky_used if victim == "lucky" else True
        if victim == "shield":
            assert not vic.shop_shield
        if victim == "killer_shield":
            assert not vic.shop_killer_shield
    elif expected == "X":
        assert vic.alive and not atk.alive
    elif expected == "B":
        assert not vic.alive and not atk.alive
    elif expected == "C":
        assert vic.alive and vic.faction == Faction.MAFIA and atk.alive
    elif expected == "H":
        assert vic.alive and atk.alive and out["miss"]
    elif expected == "P":
        assert vic.alive and atk.alive and out["saved"]
        assert not (victim == "lucky" and vic.lucky_used)
        assert not (victim == "shield" and not vic.shop_shield)
        assert not (victim == "werewolf" and vic.faction == Faction.MAFIA)
    else:  # pragma: no cover
        raise AssertionError(expected)
    if victim == "mask" and expected == "D":
        assert vic.seat in g.masked_deaths and g.last_death_role is None and not vic.shop_mask
    if source == "gun":
        assert not atk.shop_gun, "the bullet is spent whatever happens"


def test_lethal_matrix_size() -> None:
    assert len(list(_lethal_cases())) >= 250


# --------------------------------------------------------------------------------------------
# 2. Hanging: the Mafia / town vote and the confirmation trial, victim kinds x the two paths
# --------------------------------------------------------------------------------------------

LYNCH_VICTIMS = {
    # kind: (spec, outcome)  outcomes: D hanged | S survives (item spent) | K hanged + first voter dies | W suicide wins
    "citizen": ("citizen", "D"),
    "sergeant": ("sergeant", "D"),
    "mayor": ("mayor", "D"),
    "mafia": ("mafia", "D"),
    "doctor": ("doctor", "D"),
    "detective": ("detective", "D"),
    "hobo": ("hobo", "D"),
    "maniac": ("maniac", "D"),
    "werewolf": ("werewolf", "D"),
    "mage": ("mage", "D"),
    "arsonist": ("arsonist", "D"),
    "lucky_spent": (("lucky", {"lucky_used": True}), "D"),
    "lucky": ("lucky", "S"),
    "kamikaze": ("kamikaze", "K"),
    "suicide": ("suicide", "W"),
    "night_shield": (("citizen", {"shop_shield": True}), "D"),
    "killer_shield": (("citizen", {"shop_killer_shield": True}), "D"),
    "vote_shield": (("citizen", {"shop_vote_shield": True}), "S"),
    "mask": (("citizen", {"shop_mask": True}), "D"),
}
LYNCH_DISCREPANCY = {"lucky": "D6", "kamikaze": "D10"}


def _lynch_cases():
    for kind, (_, outcome) in LYNCH_VICTIMS.items():
        for path in ("direct", "trial"):
            pid = f"{kind}-{path}"
            if kind in LYNCH_DISCREPANCY:
                yield pytest.param(kind, path, outcome, id=f"{LYNCH_DISCREPANCY[kind]}:{pid}", marks=D)
            else:
                yield pytest.param(kind, path, outcome, id=pid)


@pytest.mark.parametrize(("kind", "path", "outcome"), list(_lynch_cases()))
def test_hanging_matrix(kind: str, path: str, outcome: str) -> None:
    g = build([LYNCH_VICTIMS[kind][0], "citizen", "citizen", "mafia", "mafia"], pad=2)
    # victim = player 0; players 1, 2, 3 vote for them (player 1 is the first voter by seat)
    resolve_night(g)
    day_votes(g, {1: 0, 2: 0, 3: 0})
    victim = g.players[0]
    if path == "direct":
        out = resolve_votes(g)
    else:
        seat, tie, _ = peek_votes(g)
        assert seat == 1 and not tie
        begin_lynch(g, seat, 0, 60)
        for p in g.alive_players():
            if p.user_id != victim.user_id:
                assert set_lynch_vote(g, p.user_id, True)[0]
        out = resolve_lynch(g)
    if outcome == "D":
        assert not victim.alive and out["eliminated"] == 1 and g.last_death_cause == "vote"
        if kind == "mask":
            assert g.last_death_role is None and 1 in g.masked_deaths
        else:
            assert g.last_death_role == victim.role
    elif outcome == "S":
        assert victim.alive and out["eliminated"] is None
        assert (kind != "lucky") or victim.lucky_used
        assert (kind != "vote_shield") or not victim.shop_vote_shield
    elif outcome == "K":
        assert not victim.alive
        assert not g.players[1].alive, "the first voter by seat is taken along"
        assert g.players[2].alive and g.players[3].alive
    elif outcome == "W":
        assert not victim.alive and out["winner"] == Winner.SUICIDE and g.phase == Phase.FINISHED


def test_hanging_matrix_size() -> None:
    assert len(list(_lynch_cases())) >= 38


# --------------------------------------------------------------------------------------------
# 3. The Lover (hooker): every night role is cancelled when blocked
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["mafia", "don", "maniac", "killer", "detective-shoot"])
def test_blocked_killers_do_not_kill(role: str) -> None:
    kind = "shoot" if role == "detective-shoot" else ""
    base = "detective" if role == "detective-shoot" else role
    g0 = build(["hooker", base, "citizen"])
    night(g0, (1, 2, kind))
    assert not g0.players[2].alive, "baseline: the unblocked attacker kills"
    g = build(["hooker", base, "citizen"])
    out = night(g, (0, 1), (1, 2, kind))
    assert g.players[2].alive and g.players[1].blocked and g.players[1].night_action is None
    assert out["blocked"] == [g.players[1].user_id]


def test_blocked_mafia_means_no_mafia_target() -> None:
    g = build(["hooker", "mafia", "citizen"])
    out = night(g, (0, 1), (1, 2))
    assert out["miss"] and not out["saved"] and out["killed"] is None


def test_blocked_detective_gets_no_result() -> None:
    g = build(["hooker", "detective", "mafia"])
    out = night(g, (0, 1), (1, 2))
    assert out["detective_result"] is None


def test_blocked_doctor_does_not_save() -> None:
    g = build(["hooker", "doctor", "mafia", "citizen"])
    out = night(g, (0, 1), (1, 3), (2, 3))
    assert not g.players[3].alive and not out["saved"]


def test_blocked_lawyer_does_not_cover() -> None:
    g = build(["hooker", "lawyer", "detective", "mafia"])
    out = night(g, (0, 1), (1, 3), (2, 3))
    assert out["detective_result"]["is_mafia"] is True
    g2 = build(["hooker", "lawyer", "detective", "mafia"])
    out2 = night(g2, (1, 3), (2, 3))
    assert out2["detective_result"]["is_mafia"] is False and g2.lawyer_cover == 4


def test_blocked_hobo_is_home_and_can_be_killed() -> None:
    g = build(["hooker", "hobo", "mafia", "citizen"])
    night(g, (0, 1), (1, 3), (2, 1))
    assert not g.players[1].alive, "a blocked hobo never left the house"
    g2 = build(["hooker", "hobo", "mafia", "citizen"])
    out = night(g2, (1, 3), (2, 1))
    assert g2.players[1].alive and out["miss"], "an unblocked hobo that went elsewhere is untouchable"


def test_blocked_journalist_sees_nothing() -> None:
    g = build(["hooker", "journalist", "citizen"])
    out = night(g, (0, 1), (1, 2))
    assert out["journalist_result"] is None


def test_blocked_arsonist_neither_marks_nor_burns() -> None:
    g = build(["hooker", "arsonist", "citizen"])
    night(g, (0, 1), (1, 2))
    assert g.arson_marks == []
    g2 = build(["hooker", "arsonist", "citizen"], marks=(2,))
    night(g2, (0, 1), (1, 1))
    assert g2.players[2].alive and g2.arson_marks == [3], "the fire waits"


def test_blocked_crook_steals_no_vote() -> None:
    g = build(["hooker", "crook", "citizen"])
    night(g, (0, 1), (1, 2))
    assert g.crook_mask is None


def test_blocked_snitch_cannot_win() -> None:
    g = build(["hooker", "snitch", "detective", "citizen"])
    out = night(g, (0, 1), (1, 3), (2, 3))
    assert not g.snitch_hit and out["winner"] is None


def test_blocked_mafia_member_leaves_the_vote_to_the_others() -> None:
    g = build(["hooker", "mafia", "mafia", "citizen", "citizen"])
    night(g, (0, 1), (1, 3), (2, 4))
    assert g.players[3].alive and not g.players[4].alive


def test_a_blocked_player_still_counts_as_having_acted_for_afk() -> None:
    g = build(["hooker", "doctor", "citizen"])
    night(g, (0, 1), (1, 2))
    assert g.players[1].idle_nights == 0


@D
def test_D12_two_hookers_on_each_other_are_order_dependent() -> None:
    """Whoever sits first blocks first; the second Lover is then blocked and does nothing."""
    g = build(["hooker", "hooker", "citizen"])
    out = night(g, (0, 1), (1, 0))
    assert [p.blocked for p in g.players[:2]] == [False, True]
    assert out["blocked"] == [g.players[1].user_id]


def test_hooker_blocks_whoever_she_picks_even_a_citizen() -> None:
    g = build(["hooker", "citizen"])
    night(g, (0, 1))
    assert g.players[1].blocked


def test_blocked_player_cannot_vote_but_others_can() -> None:
    g = build(["hooker", "citizen", "citizen"])
    night(g, (0, 1))
    g.phase = Phase.DAY
    begin_voting(g, 0, 60)
    assert set_vote(g, g.players[1].user_id, 4) == (False, "blocked")
    assert set_vote(g, g.players[2].user_id, 4) == (True, "ok")


@D
def test_D22_a_blocked_player_may_still_confirm_the_hanging() -> None:
    """Text: no vote 'the next day'. Engine: only the nomination vote is blocked; the yes/no trial is open."""
    g = build(["hooker", "citizen", "citizen", "citizen"])
    night(g, (0, 1))
    day_votes(g, {2: 3, 3: 2})
    begin_lynch(g, 3, 0, 60)
    assert set_lynch_vote(g, g.players[1].user_id, True) == (True, "ok")


# --------------------------------------------------------------------------------------------
# 4. Mafia kill resolution: mafia_resolve modes, ties, the Don
# --------------------------------------------------------------------------------------------

# (mode, roles of the voting block, votes (index of target or None), expected victim index or None)
MAFIA_VOTES = [
    ("majority", ("mafia", "mafia", "mafia"), (3, 3, 3), 3),
    ("majority", ("mafia", "mafia", "mafia"), (3, 3, 4), 3),
    ("majority", ("mafia", "mafia", "mafia"), (4, 3, 3), 3),
    ("majority", ("mafia", "mafia", "mafia"), (3, 3, None), 3),
    ("majority", ("mafia", "mafia", "mafia"), (3, 4, 5), None),
    ("majority", ("mafia", "mafia", "mafia"), (3, 4, None), None),
    ("majority", ("mafia", "mafia", "mafia"), (3, None, None), None),
    ("majority", ("mafia", "mafia"), (3, 3), 3),
    ("majority", ("mafia", "mafia"), (3, None), 3),
    ("majority", ("mafia", "mafia"), (3, 4), None),
    ("majority", ("mafia",), (3,), 3),
    ("majority", ("don", "mafia", "mafia"), (4, 3, 3), 3),
    ("majority", ("don", "mafia", "mafia"), (3, 4, 5), 3),
    ("majority", ("don", "mafia", "mafia"), (3, 4, None), 3),
    ("majority", ("don", "mafia", "mafia"), (None, 3, 4), None),
    ("majority", ("don", "mafia"), (3, 4), 3),
    ("majority", ("don", "mafia"), (4, 3), 4),
    ("majority", ("mafia", "don"), (3, 4), 4),
    ("unanimous", ("mafia", "mafia", "mafia"), (3, 3, 3), 3),
    ("unanimous", ("mafia", "mafia", "mafia"), (3, 3, None), None),
    ("unanimous", ("mafia", "mafia", "mafia"), (3, 3, 4), None),
    ("unanimous", ("don", "mafia"), (3, 3), 3),
    ("unanimous", ("don", "mafia"), (3, 4), None),
    ("first", ("mafia", "mafia", "mafia"), (4, 3, 3), 4),
    ("first", ("mafia", "mafia", "mafia"), (None, 3, 4), 3),
    ("first", ("mafia", "don"), (3, 4), 3),
]


@pytest.mark.parametrize(("mode", "block", "votes", "victim"), MAFIA_VOTES)
def test_mafia_target_resolution(mode, block, votes, victim) -> None:
    g = build(list(block) + ["citizen", "citizen", "citizen"], resolve=mode)
    n = len(block)
    cits = list(range(n, n + 3))
    # votes are given as 3/4/5; translate them to the three citizens that follow the voting block
    out = night(g, *[(i, cits[t - 3]) for i, t in enumerate(votes) if t is not None])
    dead = [c - n + 3 for c in cits if not g.players[c].alive]
    assert dead == ([] if victim is None else [victim])
    assert out["miss"] == (victim is None)


def test_lawyer_journalist_killer_do_not_vote_in_the_mafia_kill() -> None:
    g = build(["lawyer", "journalist", "citizen", "citizen"])
    out = night(g, (0, 2), (1, 2))
    assert out["miss"] and g.players[2].alive


def test_mafia_cannot_aim_at_the_own_faction() -> None:
    g = build(["mafia", "don", "lawyer", "killer", "journalist"])
    for actor in (0, 1, 3):
        for tgt in (1, 2, 4):
            if actor != tgt:
                assert act(g, actor, tgt) == (False, "no_teamkill"), (actor, tgt)
    assert act(g, 2, 0) == (True, "ok"), "the Lawyer may cover a partner"
    assert act(g, 4, 0) == (True, "ok"), "the Spy may watch a partner"


def test_mafia_and_maniac_on_one_victim_is_one_death() -> None:
    g = build(["mafia", "maniac", "citizen"])
    out = night(g, (0, 2), (1, 2))
    assert out["deaths"] == [3] and out["killed"] == 3


def test_mafia_and_maniac_on_different_victims_is_two_deaths() -> None:
    g = build(["mafia", "maniac", "citizen", "citizen"])
    out = night(g, (0, 2), (1, 3))
    assert sorted(out["deaths"]) == [3, 4]


def test_doctor_saves_the_mafia_victim_not_the_maniac_one() -> None:
    g = build(["mafia", "maniac", "doctor", "citizen", "citizen"])
    out = night(g, (0, 3), (1, 4), (2, 3))
    assert g.players[3].alive and not g.players[4].alive and out["saved"]


def test_executioner_ignores_the_doctor_but_the_night_is_still_reported_saved() -> None:
    g = build(["mafia", "killer", "doctor", "citizen"])
    out = night(g, (0, 3), (1, 3), (2, 3))
    assert not g.players[3].alive, "the Executioner's bullet goes through the Doctor"
    assert out["saved"] is True, "...yet the saved flag stays up"


@D
def test_D16_day_announcement_says_saved_although_the_victim_died() -> None:
    from tezmafia import texts
    from tezmafia.i18n import t

    g = build(["mafia", "killer", "doctor", "citizen"])
    night(g, (0, 3), (1, 3), (2, 3))
    assert t("en", "day.saved") in texts.day_group(g, True, "en")
    assert g.last_death_seat == 4, "the engine knows who died"


@D
def test_D16_two_deaths_in_a_night_only_the_last_is_announced() -> None:
    g = build(["mafia", "maniac", "citizen", "citizen"])
    night(g, (0, 2), (1, 3))
    assert sorted(g.night_deaths) == [3, 4] and g.last_death_seat == 4


@D
def test_D16_a_maniac_kill_is_announced_as_a_mafia_miss() -> None:
    from tezmafia import texts
    from tezmafia.i18n import t

    g = build(["maniac", "citizen", "citizen"])
    out = night(g, (0, 1))
    assert out["miss"] is True and g.last_death_seat == 2
    assert t("en", "day.miss") in texts.day_group(g, True, "en")


def test_only_the_first_doctor_maniac_killer_act() -> None:
    g = build(["doctor", "doctor", "mafia", "citizen"])
    night(g, (0, 1), (1, 3), (2, 3))
    assert not g.players[3].alive, "the second Doctor's save is ignored"
    g2 = build(["maniac", "maniac", "citizen", "citizen"])
    night(g2, (0, 2), (1, 3))
    assert g2.players[2].alive is False and g2.players[3].alive is True, "only the first Maniac hunts"
    g3 = build(["killer", "killer", "citizen", "citizen"])
    night(g3, (0, 2), (1, 3))
    assert not g3.players[2].alive and g3.players[3].alive


def test_doctor_may_save_themselves_only_once() -> None:
    g = build(["doctor", "mafia", "citizen"])
    night(g, (0, 0), (1, 0))
    assert g.players[0].alive and g.players[0].doctor_self_used
    begin_night(g, 0, 60)
    assert act(g, 0, 0) == (False, "self_used")
    assert act(g, 0, 2) == (True, "ok")


def test_a_blocked_doctors_self_save_is_not_used_up() -> None:
    g = build(["doctor", "hooker", "citizen"])
    night(g, (0, 0), (1, 0))
    assert not g.players[0].doctor_self_used


# --------------------------------------------------------------------------------------------
# 5. Executioner, Enchanter, Kamikaze, Traitor: the reactive roles
# --------------------------------------------------------------------------------------------

def test_executioner_dies_when_aiming_at_the_detective_whatever_protects_them() -> None:
    g = build(["killer", "detective", "doctor"])
    night(g, (0, 1), (2, 1))
    assert not g.players[0].alive and g.players[1].alive


@D
def test_D19_executioner_also_dies_when_the_detective_was_killed_earlier_that_night() -> None:
    g = build(["killer", "detective", "mafia"])
    night(g, (0, 1), (2, 1))
    assert not g.players[0].alive and not g.players[1].alive


@D
def test_D9_enchanter_reflects_onto_the_first_mafia_by_seat_not_the_voter() -> None:
    g = build(["mafia", "don", "mage"])
    night(g, (1, 2))  # only the Don voted
    assert not g.players[0].alive and g.players[1].alive and g.players[2].alive


def test_enchanter_reflects_every_kind_of_attack_but_not_the_trial() -> None:
    for attacker in ("maniac", "killer"):
        g = build([attacker, "mage"])
        night(g, (0, 1))
        assert g.players[1].alive and not g.players[0].alive, attacker


@D
def test_D10_kamikaze_blast_ignores_the_victims_protections() -> None:
    """Hanged Kamikaze takes the first voter by seat even if that voter is a Lucky One."""
    g = build(["lucky", "kamikaze", "citizen", "citizen"])
    resolve_night(g)
    day_votes(g, {0: 1, 2: 1, 3: 1})
    resolve_votes(g)
    assert not g.players[1].alive and not g.players[0].alive and g.players[0].lucky_used is False


def test_traitor_joins_the_mafia_and_then_counts_for_them() -> None:
    g = build(["mafia", "werewolf", "citizen"], pad=0)
    night(g, (0, 1))
    assert g.players[1].alive and g.players[1].faction == Faction.MAFIA
    assert win_check(g) == Winner.MAFIA, "2 mafia-side against 1 citizen"


def test_traitor_cannot_join_the_mafia_vote() -> None:
    g = build(["mafia", "werewolf", "citizen"])
    night(g, (0, 1))
    begin_night(g, 0, 60)
    assert act(g, 1, 2) == (False, "no_action"), "a converted Traitor has no vote in the kill"


# --------------------------------------------------------------------------------------------
# 6. Information roles: Detective, Spy, Dervish, Informer, Swindler
# --------------------------------------------------------------------------------------------

# target -> expected "is_mafia" in the Detective's answer
CHECK_TABLE = [
    ("mafia", True), ("lawyer", True), ("journalist", True), ("killer", True),
    disc("D2", "don", False, id="don-looks-clean"),
    ("citizen", False), ("sergeant", False), ("doctor", False), ("hooker", False), ("hobo", False),
    ("lucky", False), ("kamikaze", False), ("mayor", False), ("werewolf", False),
    ("maniac", False), ("suicide", False), ("arsonist", False), ("mage", False), ("crook", False),
    ("snitch", False),
    (("mafia", {"shop_fake_id": True}), False),
    (("mafia", {"shop_mask": True}), True),
    (("mafia", {"shop_shield": True}), True),
    (("citizen", {"shop_fake_id": True}), False),
    (("werewolf", {"faction": "mafia"}), True),
]


@pytest.mark.parametrize(("target", "is_mafia"), CHECK_TABLE)
def test_detective_check_table(target, is_mafia) -> None:
    g = build(["detective", target])
    out = night(g, (0, 1))
    assert out["detective_result"] == {"seat": 2, "is_mafia": is_mafia, "detective_id": 10}


def test_lawyer_cover_makes_any_partner_clean() -> None:
    g = build(["detective", "mafia", "lawyer"])
    out = night(g, (0, 1), (2, 1))
    assert out["detective_result"]["is_mafia"] is False
    g2 = build(["detective", "killer", "lawyer"])
    assert night(g2, (0, 1), (2, 1))["detective_result"]["is_mafia"] is False
    g3 = build(["detective", "mafia", "lawyer", "citizen"])
    assert night(g3, (0, 1), (2, 3))["detective_result"]["is_mafia"] is True, "covering someone else does nothing"


def test_the_check_sees_the_state_before_the_night_happens() -> None:
    """A Traitor converted this very night still reads as a civilian."""
    g = build(["detective", "werewolf", "mafia"])
    out = night(g, (0, 1), (2, 1))
    assert g.players[1].faction == Faction.MAFIA and out["detective_result"]["is_mafia"] is False


def test_detective_may_not_shoot_the_first_night_nor_check_oneself() -> None:
    g = build(["detective", "citizen"], night_no=1)
    assert act(g, 0, 1, "shoot") == (False, "no_first_shoot")
    assert act(g, 0, 0) == (False, "no_self")
    assert act(g, 0, 1) == (True, "ok")
    g2 = build(["detective", "citizen"], night_no=2)
    assert act(g2, 0, 1, "shoot") == (True, "ok")


@D
def test_D17_a_detective_killed_the_same_night_still_gets_the_answer_and_still_shoots() -> None:
    g = build(["detective", "mafia", "maniac", "citizen"])
    night(g, (0, 3, "shoot"), (1, 0))
    assert not g.players[0].alive and not g.players[3].alive, "the dead Detective's shot lands"
    g2 = build(["detective", "mafia", "citizen"])
    out2 = night(g2, (0, 1), (1, 0))
    assert out2["detective_result"]["seat"] == 2 and not g2.players[0].alive


HELPERS = ["detective", "sergeant", "doctor", "hooker", "hobo", "mayor"]
NOT_HELPERS = [r.value for r in Role if r.value not in HELPERS]


@pytest.mark.parametrize("watched", [*[(r, True) for r in HELPERS], *[(r, False) for r in NOT_HELPERS]])
def test_spy_says_whether_the_resident_is_a_helper(watched) -> None:
    role, helper = watched
    g = build(["journalist", role])
    out = night(g, (0, 1))
    assert out["journalist_result"]["helper"] is helper


def test_spy_lists_every_visitor_in_seat_order_but_not_blocked_ones() -> None:
    g = build(["journalist", "mafia", "doctor", "detective", "hooker", "maniac", "citizen"], pad=2)
    # watched = seat 7 (index 6). The hooker blocks the maniac, who would have come.
    out = night(g, (0, 6), (1, 6), (2, 6), (3, 6), (4, 5), (5, 6))
    assert out["journalist_result"]["visitors"] == [2, 3, 4]
    assert out["journalist_result"]["seat"] == 7


def test_spy_never_lists_themselves_and_sees_an_empty_door() -> None:
    g = build(["journalist", "citizen"])
    assert night(g, (0, 1))["journalist_result"]["visitors"] == []


@D
def test_D3_dervish_information_is_computed_wrongly_and_never_delivered() -> None:
    """Text: the Dervish sees who comes to the door he sleeps at. Engine: `hobo_seen` is the list of the
    night's mafia victim, maniac victim and protected seat (not the visitors of his door), and neither the
    resolve result nor any handler ever gives it to the player."""
    g = build(["hobo", "mafia", "maniac", "doctor", "citizen", "citizen"])
    out = night(g, (0, 4), (1, 4), (2, 5), (3, 4))
    assert g.hobo_seen == {"seats": [5, 6, 5], "hobo_id": 10}
    assert "hobo_seen" not in out


@D
def test_D4_dervish_who_sleeps_at_the_victims_door_dies_with_them() -> None:
    g = build(["mafia", "citizen", "hobo", "doctor"])
    night(g, (0, 1), (2, 1))
    assert not g.players[1].alive and not g.players[2].alive


def test_dervish_cannot_stay_at_his_own_door() -> None:
    g = build(["hobo", "citizen"])
    assert act(g, 0, 0) == (False, "no_self")


def test_informer_wins_when_the_detective_checks_the_same_person() -> None:
    g = build(["snitch", "detective", "citizen"])
    out = night(g, (0, 2), (1, 2))
    assert out["winner"] == Winner.SNITCH and g.phase == Phase.FINISHED


@pytest.mark.parametrize(
    ("snitch_target", "detective_target", "kind"),
    [(2, 3, ""), (2, 2, "shoot"), (3, 2, ""), (2, None, ""), (None, 2, "")],
)
def test_informer_needs_the_same_target_and_a_check_not_a_shot(snitch_target, detective_target, kind) -> None:
    g = build(["snitch", "detective", "citizen", "citizen"])
    acts = []
    if snitch_target is not None:
        acts.append((0, snitch_target))
    if detective_target is not None:
        acts.append((1, detective_target, kind))
    out = night(g, *acts)
    assert out["winner"] is None and not g.snitch_hit


@D
def test_D18_informer_killed_the_same_night_still_wins() -> None:
    g = build(["snitch", "detective", "mafia", "citizen"])
    out = night(g, (0, 3), (1, 3), (2, 0))
    assert not g.players[0].alive and out["winner"] == Winner.SNITCH


# --- Swindler (crook) and the vote steal -----------------------------------------------------

def _crook_day(extra_votes: dict[int, int], crook_vote: int | None, victim: int = 1, **kw):
    g = build(["crook", "citizen", "citizen", "citizen", "citizen", "mayor"], **kw)
    night(g, (0, victim))
    votes = dict(extra_votes)
    if crook_vote is not None:
        votes[0] = crook_vote
    day_votes(g, votes)
    return g


def test_swindler_steals_the_victims_vote() -> None:
    g = _crook_day({1: 2}, crook_vote=3)
    seat, tie, tally = peek_votes(g)
    assert g.players[1].vote == 4 and tally == {4: 2} and seat == 4 and not tie


def test_swindler_without_a_vote_steals_nothing() -> None:
    g = _crook_day({1: 2}, crook_vote=None)
    assert g.players[1].vote == 3


def test_swindler_who_died_steals_nothing() -> None:
    g = _crook_day({1: 2}, crook_vote=3)
    g.players[0].alive = False
    g.players[1].vote = 3
    peek_votes(g)
    assert g.players[1].vote == 3


@D
def test_D15_swindler_can_make_the_victim_vote_for_themselves_and_double_a_mayors_vote() -> None:
    g = _crook_day({1: 2}, crook_vote=1)
    peek_votes(g)
    assert g.players[1].vote == 2, "a forced self-vote, impossible through set_vote"
    g2 = _crook_day({}, crook_vote=3, victim=5)
    seat, tie, tally = peek_votes(g2)
    assert tally == {4: 3}, "the Mayor's stolen double vote plus the Swindler's own"


# --- Arsonist --------------------------------------------------------------------------------

def test_arsonist_marks_accumulate_without_duplicates_and_ignite_clears_them() -> None:
    g = build(["arsonist", "citizen", "citizen", "citizen"])
    night(g, (0, 1))
    assert g.arson_marks == [2]
    begin_night(g, 0, 60)
    night(g, (0, 1))
    assert g.arson_marks == [2], "marking the same house twice changes nothing"
    begin_night(g, 0, 60)
    night(g, (0, 2))
    assert g.arson_marks == [2, 3]
    begin_night(g, 0, 60)
    night(g, (0, 0))
    assert [p.alive for p in g.players[:4]] == [True, False, False, True]
    assert g.arson_marks == [] and g.arson_kills == 2


def test_arsonist_fire_ignores_the_doctor_and_burns_lucky_only_once() -> None:
    g = build(["arsonist", "doctor", "lucky"], marks=(1, 2))
    night(g, (0, 0), (1, 1))  # the Doctor saves themself
    assert not g.players[1].alive, "protection does not stop fire"
    assert g.players[2].alive and g.players[2].lucky_used
    assert g.arson_kills == 1


def test_three_burned_lives_win_the_game_for_the_arsonist() -> None:
    g = build(["arsonist", "citizen", "citizen", "citizen", "citizen"], marks=(1, 2, 3))
    out = night(g, (0, 0))
    assert g.arson_kills == 3 and out["winner"] == Winner.ARSONIST


def test_arsonist_igniting_with_no_marks_burns_nothing() -> None:
    g = build(["arsonist", "citizen"])
    night(g, (0, 0))
    assert g.arson_kills == 0 and g.players[1].alive


@D
def test_D5_marks_that_already_died_still_count_as_burned_lives() -> None:
    """Text: 'Three lives burned and the Arsonist wins.' Engine counts a dead mark as a burned life."""
    g = build(["arsonist", "citizen", "citizen", "citizen", "citizen"], marks=(1, 2, 3))
    for i in (1, 2, 3):
        g.players[i].alive = False
    out = night(g, (0, 0))
    assert g.arson_kills == 3 and out["winner"] == Winner.ARSONIST


@D
def test_D21_attackers_killed_earlier_the_same_night_act_unevenly() -> None:
    """Mafia/Maniac hits resolve first. A dead Executioner, Arsonist or pistol owner does not act any more,
    but a dead Detective's shot still lands."""
    g = build(["killer", "maniac", "citizen"])
    night(g, (0, 2), (1, 0))
    assert not g.players[0].alive and g.players[2].alive, "dead Executioner: no shot"
    g = build(["arsonist", "maniac", "citizen"], marks=(2,))
    night(g, (0, 0), (1, 0))
    assert not g.players[0].alive and g.players[2].alive, "dead Arsonist: no fire"
    g = build([("citizen", {"shop_gun": True}), "maniac", "citizen"])
    night(g, (0, 2), (1, 0))
    assert not g.players[0].alive and g.players[2].alive, "dead pistol owner: no shot"
    g = build(["detective", "maniac", "citizen"])
    night(g, (0, 2, "shoot"), (1, 0))
    assert not g.players[0].alive and not g.players[2].alive, "dead Detective: the shot still lands"


# --- Sergeant --------------------------------------------------------------------------------

def test_sergeant_becomes_detective_when_the_detective_dies_at_night() -> None:
    g = build(["detective", "sergeant", "mafia"])
    night(g, (2, 0))
    assert g.players[1].role == "detective" and g.players[1].alive


def test_sergeant_stays_while_a_detective_lives_and_promotes_after_a_hanging() -> None:
    g = build(["detective", "sergeant", "citizen"])
    night(g, (0, 2))
    assert g.players[1].role == "sergeant"
    day_votes(g, {1: 0, 2: 0, 3: 0})
    resolve_votes(g)
    assert not g.players[0].alive and g.players[1].role == "detective"


def test_promoted_sergeant_is_a_night_role_afterwards() -> None:
    g = build(["detective", "sergeant", "mafia"])
    night(g, (2, 0))
    begin_night(g, 0, 60)
    assert act(g, 1, 2) == (True, "ok")


# --- Gun --------------------------------------------------------------------------------------

def test_pistol_fires_once_from_the_first_night_and_not_at_oneself() -> None:
    g = build([("citizen", {"shop_gun": True}), "citizen"], night_no=1)
    assert act(g, 0, 0) == (False, "no_self")
    night(g, (0, 1))
    assert not g.players[1].alive and not g.players[0].shop_gun


def test_pistol_is_dead_weight_for_a_night_role() -> None:
    g = build([("doctor", {"shop_gun": True}), "citizen", "citizen"])
    night(g, (0, 1))
    assert g.players[1].alive and g.players[0].shop_gun and g.players[0].detective_mode is None


@D
def test_D7_a_pistol_owner_who_never_shoots_is_removed_as_idle_after_two_nights() -> None:
    g = build([("citizen", {"shop_gun": True}), "citizen"])
    resolve_night(g)
    assert g.players[0].alive and g.players[0].idle_nights == 1
    begin_night(g, 0, 60)
    out = resolve_night(g)
    assert not g.players[0].alive and out["afk"] == [1]


def test_blocked_pistol_stays_loaded() -> None:
    g = build(["hooker", ("citizen", {"shop_gun": True}), "citizen"])
    night(g, (0, 1), (1, 2))
    assert g.players[2].alive and g.players[1].shop_gun


# --- Idle (AFK) -------------------------------------------------------------------------------

def test_a_night_role_idle_two_nights_in_a_row_is_removed() -> None:
    g = build(["doctor", "citizen"])
    out1 = resolve_night(g)
    assert g.players[0].alive and out1["afk"] == [] and g.players[0].idle_nights == 1
    begin_night(g, 0, 60)
    out2 = resolve_night(g)
    assert not g.players[0].alive and out2["afk"] == [1]
    assert g.chronicle[-1]["cause"] == "afk" and 1 in g.afk_deaths


def test_acting_resets_the_idle_counter() -> None:
    g = build(["doctor", "citizen"])
    resolve_night(g)
    begin_night(g, 0, 60)
    night(g, (0, 1))
    assert g.players[0].alive and g.players[0].idle_nights == 0
    begin_night(g, 0, 60)
    resolve_night(g)
    assert g.players[0].alive


@pytest.mark.parametrize("role", sorted(r.value for r in Role if r not in NIGHT_ROLES))
def test_roles_without_a_night_job_are_never_idle(role: str) -> None:
    g = build([role, "detective", "citizen"])  # a working Detective keeps the Sergeant a Sergeant
    for _ in range(4):
        night(g, (1, 2))
        begin_night(g, 0, 60)
    assert g.players[0].alive and g.players[0].idle_nights == 0


@pytest.mark.parametrize("role", sorted(r.value for r in NIGHT_ROLES))
def test_every_night_role_is_removed_after_two_idle_nights(role: str) -> None:
    g = build([role, "citizen", "citizen"])
    resolve_night(g)
    begin_night(g, 0, 60)
    out = resolve_night(g)
    assert not g.players[0].alive and out["afk"] == [1]


@D
def test_D6_lucky_one_also_survives_an_idle_removal() -> None:
    """A Lucky One holding a pistol who sits out two nights uses the 'spare life' on the idle removal."""
    g = build([("lucky", {"shop_gun": True}), "citizen"])
    resolve_night(g)
    begin_night(g, 0, 60)
    out = resolve_night(g)
    assert g.players[0].alive and g.players[0].lucky_used and out["afk"] == []


# --- Hobo immunity, shared by every attack ------------------------------------------------------

@D
def test_D4_dervish_away_from_home_is_untouchable_by_every_kind_of_attack() -> None:
    for attacker, kind in (("mafia", ""), ("maniac", ""), ("killer", ""), ("detective", "shoot")):
        g = build([attacker, "hobo", "citizen"])
        out = night(g, (0, 1, kind), (1, 2))
        assert g.players[1].alive and out["miss"], attacker


# --------------------------------------------------------------------------------------------
# 7. Ordered pairs of night roles: every A x B, three scenarios, compared with a rule-based spec
#    S1 both pick the same citizen T | S2 A picks B (B idle) | S3 A picks B and B picks A
# --------------------------------------------------------------------------------------------

# variant -> (role, mode); "ignite" is the Arsonist picking themself with the other two houses marked
VARIANTS = {
    "mafia": ("mafia", ""), "don": ("don", ""), "killer": ("killer", ""), "maniac": ("maniac", ""),
    "shoot": ("detective", "shoot"), "check": ("detective", "check"), "doctor": ("doctor", ""),
    "hooker": ("hooker", ""), "lawyer": ("lawyer", ""), "hobo": ("hobo", ""), "journalist": ("journalist", ""),
    "mark": ("arsonist", "mark"), "ignite": ("arsonist", "ignite"), "crook": ("crook", ""), "snitch": ("snitch", ""),
}
PAIRS = [
    (a, b) for a, b in itertools.permutations(VARIANTS, 2) if VARIANTS[a][0] != VARIANTS[b][0]
]
SCENARIOS = ("same-target", "A-on-B", "mutual")
HELPER_ROLES = {"detective", "sergeant", "doctor", "hooker", "hobo", "mayor"}
LETHAL_RESPECTING_PROTECTION = {"mafia", "don", "maniac"}


def _plan(a: str, b: str, scenario: str) -> dict[int, int]:
    """Who acts on whom (indexes). Idle players are absent."""
    plan: dict[int, int] = {}
    wanted = {"same-target": {0: 2, 1: 2}, "A-on-B": {0: 1}, "mutual": {0: 1, 1: 0}}[scenario]
    for idx, tgt in wanted.items():
        plan[idx] = idx if VARIANTS[(a, b)[idx]][1] == "ignite" else tgt
    return plan


def _spec(a: str, b: str, scenario: str):
    """The expected outcome, written from the rules (see the module docstring), not from the engine code."""
    roles = [VARIANTS[a][0], VARIANTS[b][0], "citizen"]
    mode = [VARIANTS[a][1], VARIANTS[b][1], ""]
    fac = [ROLE_FACTION[Role(r)].value for r in roles]
    plan = _plan(a, b, scenario)
    # 1. refusals: the Mafia side never aims at its own faction
    refused = set()
    for i, tgt in plan.items():
        if roles[i] in ("mafia", "don", "killer") and fac[tgt] == "mafia" and tgt != i:
            refused.add(i)
    acts = {i: t for i, t in plan.items() if i not in refused}
    alive = [True, True, True]
    # 2. the Lover blocks, in seat order; a blocked Lover who has not acted yet loses her action
    blocked: set[int] = set()
    for i in range(2):
        if roles[i] == "hooker" and i in acts and acts[i] != i:
            acts.pop(acts[i], None)
            blocked.add(plan[i])
    # 3. cover, protection, targets
    covered = {acts[i] for i in range(2) if roles[i] == "lawyer" and i in acts}
    protect = next((acts.get(i) for i in range(2) if roles[i] == "doctor"), None)
    voters = [i for i in range(2) if roles[i] in ("mafia", "don") and i in acts]
    mafia_target = None
    if voters:
        votes = [acts[i] for i in voters]
        if len(set(votes)) == 1:
            mafia_target = votes[0]
        else:  # a tie: only the Don breaks it
            don = next((i for i in voters if roles[i] == "don"), None)
            mafia_target = acts[don] if don is not None else None
    maniac = next((i for i in range(2) if roles[i] == "maniac"), None)
    maniac_target = acts.get(maniac) if maniac is not None else None
    hobos = [i for i in range(2) if roles[i] == "hobo"]

    def away(v: int) -> bool:
        return roles[v] == "hobo" and v in acts and acts[v] != v

    def kill(v: int | None, ignore_protect: bool = False) -> None:
        if v is None:
            return
        if protect == v and not ignore_protect:
            return
        if away(v):
            return
        if alive[v]:
            alive[v] = False
            for h in hobos:
                if alive[h] and acts.get(h) == v:
                    alive[h] = False

    kill(mafia_target)
    if maniac_target is not None and maniac_target != mafia_target:
        kill(maniac_target)
    killer = next((i for i in range(2) if roles[i] == "killer" and alive[i] and i in acts), None)
    if killer is not None:
        if roles[acts[killer]] == "detective":
            alive[killer] = False
        else:
            kill(acts[killer], ignore_protect=True)
    det = next((i for i in range(2) if roles[i] == "detective"), None)
    if det is not None and mode[det] == "shoot" and det in acts:
        kill(acts[det])
    ars = next((i for i in range(2) if roles[i] == "arsonist" and alive[i]), None)
    if ars is not None and mode[ars] == "ignite" and ars in acts:
        for victim in (j for j in range(3) if j != ars):
            kill(victim, ignore_protect=True)
    result = {"dead": {i for i in range(3) if not alive[i]}, "blocked": blocked}
    # 4. information
    result["check"] = None
    if det is not None and mode[det] == "check" and det in acts:
        v = acts[det]
        looks = fac[v] == "mafia" and roles[v] != "don" and v not in covered
        result["check"] = (v + 1, looks)
    result["spy"] = None
    jr = next((i for i in range(2) if roles[i] == "journalist"), None)
    if jr is not None and jr in acts:
        w = acts[jr]
        visitors = [i + 1 for i in range(3) if acts.get(i) == w and i != jr]
        result["spy"] = (w + 1, visitors, roles[w] in HELPER_ROLES)
    sn = next((i for i in range(2) if roles[i] == "snitch"), None)
    result["snitch"] = bool(
        sn is not None and det is not None and sn in acts and det in acts
        and acts[sn] == acts[det] and mode[det] != "shoot"
    )
    result["refused"] = refused
    return result


def _pair_cases():
    for a, b in PAIRS:
        for scenario in SCENARIOS:
            yield pytest.param(a, b, scenario, id=f"{a}+{b}:{scenario}")


@pytest.mark.parametrize(("a", "b", "scenario"), list(_pair_cases()))
def test_ordered_pairs(a: str, b: str, scenario: str) -> None:
    expected = _spec(a, b, scenario)
    marks = tuple(j for j in range(3) if j != next((i for i in range(2) if VARIANTS[(a, b)[i]][1] == "ignite"), -1))
    has_fire = "ignite" in (a, b)
    g = build([VARIANTS[a][0], VARIANTS[b][0], "citizen"], marks=marks if has_fire else ())
    plan = _plan(a, b, scenario)
    refused = set()
    for i, tgt in plan.items():
        ok, why = act(g, i, tgt, "shoot" if VARIANTS[(a, b)[i]][1] == "shoot" else "")
        if not ok:
            assert why == "no_teamkill", (i, why)
            refused.add(i)
    assert refused == expected["refused"]
    out = resolve_night(g)
    assert {i for i in range(3) if not g.players[i].alive} == expected["dead"]
    assert set(out["blocked"]) == {g.players[i].user_id for i in expected["blocked"]}
    det = out["detective_result"]
    assert (None if det is None else (det["seat"], det["is_mafia"])) == expected["check"]
    spy = out["journalist_result"]
    assert (None if spy is None else (spy["seat"], spy["visitors"], spy["helper"])) == expected["spy"]
    assert g.snitch_hit == expected["snitch"]


def test_ordered_pair_grid_size() -> None:
    assert len(list(_pair_cases())) == 3 * len(PAIRS) and len(PAIRS) >= 200


# --------------------------------------------------------------------------------------------
# 8. Day: votes, the Mayor, ties, the trial, immunities
# --------------------------------------------------------------------------------------------

DAY_SPEC = ["mayor", "citizen", "citizen", "citizen", "citizen", "mafia"]

# votes {voter: target} -> (leading seat or None, tie, tally {seat: weight})
TALLY_CASES = [
    ({}, None, False, {}),
    ({1: 2}, 3, False, {3: 1}),
    ({1: 3, 2: 3, 3: 4}, 4, False, {4: 2, 5: 1}),
    ({1: 2, 2: 3}, None, True, {3: 1, 4: 1}),
    ({0: 3}, 4, False, {4: 2}),
    ({0: 3, 1: 3}, 4, False, {4: 3}),
    ({0: 3, 1: 4, 2: 4}, None, True, {4: 2, 5: 2}),
    ({0: 3, 1: 4, 2: 4, 3: 4}, 5, False, {4: 2, 5: 3}),
    ({0: 3, 1: 2, 3: 2, 4: 2}, 3, False, {4: 2, 3: 3}),
]


@pytest.mark.parametrize(("votes", "lead", "tie", "tally"), TALLY_CASES)
def test_vote_tally_and_the_mayors_double_vote(votes, lead, tie, tally) -> None:
    g = build(DAY_SPEC, pad=0)
    day_votes(g, votes)
    seat, is_tie, got = peek_votes(g)
    assert (seat, is_tie, got) == (lead, tie, tally)
    out = resolve_votes(g)
    assert out["tie"] == tie
    assert (out["eliminated"] is None) == (lead is None)
    assert out["eliminated"] == lead


def test_nobody_may_vote_for_themselves_a_dead_player_or_out_of_phase() -> None:
    g = build(DAY_SPEC, pad=0)
    g.phase = Phase.DAY
    assert set_vote(g, g.players[1].user_id, 3) == (False, "not_voting")
    begin_voting(g, 0, 60)
    assert set_vote(g, g.players[1].user_id, 2) == (False, "no_self")
    g.players[3].alive = False
    assert set_vote(g, g.players[1].user_id, 4) == (False, "bad_target")
    assert set_vote(g, g.players[3].user_id, 2) == (False, "dead")
    assert set_vote(g, g.players[1].user_id, 3) == (True, "ok")
    assert set_vote(g, g.players[1].user_id, None) == (True, "cleared") and g.players[1].vote is None


# trial: (yes, no) -> confirmed
@pytest.mark.parametrize(
    ("yes", "no", "confirmed"),
    [(3, 0, True), (1, 0, True), (0, 0, False), (1, 1, False), (2, 3, False), (3, 2, True), (0, 3, False)],
)
def test_the_trial_needs_more_yes_than_no(yes: int, no: int, confirmed: bool) -> None:
    g = build(["citizen"] * 7, pad=0)
    begin_lynch(g, 1, 0, 60)
    voters = [p for p in g.players if p.seat != 1]
    for p in voters[:yes]:
        assert set_lynch_vote(g, p.user_id, True)[0]
    for p in voters[yes:yes + no]:
        assert set_lynch_vote(g, p.user_id, False)[0]
    out = resolve_lynch(g)
    assert out["confirmed"] is confirmed and (out["eliminated"] == 1) is confirmed
    assert (out["yes"], out["no"]) == (yes, no)


def test_the_accused_and_the_dead_do_not_vote_in_the_trial() -> None:
    g = build(["citizen"] * 5, pad=0)
    g.players[4].alive = False
    begin_lynch(g, 1, 0, 60)
    assert set_lynch_vote(g, g.players[0].user_id, True) == (False, "no_self")
    assert set_lynch_vote(g, g.players[4].user_id, True) == (False, "dead")
    assert set_lynch_vote(g, g.players[1].user_id, True) == (True, "ok")


@D
def test_D8_the_mayors_double_vote_does_not_apply_to_the_confirmation() -> None:
    g = build(["mayor", "citizen", "citizen", "citizen"], pad=0)
    begin_lynch(g, 4, 0, 60)
    set_lynch_vote(g, g.players[0].user_id, True)
    set_lynch_vote(g, g.players[1].user_id, False)
    out = resolve_lynch(g)
    assert (out["yes"], out["no"], out["confirmed"]) == (1, 1, False)


@D
@pytest.mark.parametrize("path", ["direct", "trial"])
def test_D1_lawyer_cover_also_saves_the_partner_from_the_gallows(path: str) -> None:
    """Text: the Lawyer only clears someone of the Detective's check. Engine: the same cover voids the hanging."""
    g = build(["lawyer", "mafia", "citizen", "citizen", "citizen"], pad=0)
    night(g, (0, 1))
    day_votes(g, {2: 1, 3: 1, 4: 1})
    if path == "direct":
        out = resolve_votes(g)
    else:
        begin_lynch(g, 2, 0, 60)
        for p in (g.players[2], g.players[3], g.players[4]):
            set_lynch_vote(g, p.user_id, True)
        out = resolve_lynch(g)
    assert g.players[1].alive and out["eliminated"] is None


@pytest.mark.parametrize("path", ["direct", "trial"])
def test_lawyer_cover_of_someone_else_or_a_blocked_lawyer_saves_nobody(path: str) -> None:
    for blocked in (False, True):
        spec = ["lawyer", "mafia", "citizen", "citizen", "citizen", "hooker"]
        g = build(spec, pad=0)
        acts = [(0, 2 if not blocked else 1)]
        if blocked:
            acts.append((5, 0))
        night(g, *acts)
        day_votes(g, {2: 1, 3: 1, 4: 1})
        if path == "direct":
            out = resolve_votes(g)
        else:
            begin_lynch(g, 2, 0, 60)
            for p in (g.players[2], g.players[3], g.players[4]):
                set_lynch_vote(g, p.user_id, True)
            out = resolve_lynch(g)
        assert not g.players[1].alive and out["eliminated"] == 2


def test_lawyer_cover_expires_with_the_next_night() -> None:
    g = build(["lawyer", "mafia", "citizen", "citizen"], pad=0)
    night(g, (0, 1))
    assert g.lawyer_cover == 2
    begin_night(g, 0, 60)
    assert g.lawyer_cover is None


@pytest.mark.parametrize("path", ["direct", "trial"])
def test_trial_shield_works_once(path: str) -> None:
    g = build([("citizen", {"shop_vote_shield": True}), "citizen", "citizen", "citizen", "mafia"], pad=0)
    for expect_alive in (True, False):
        day_votes(g, {1: 0, 2: 0, 3: 0})
        if path == "direct":
            resolve_votes(g)
        else:
            begin_lynch(g, 1, 0, 60)
            for p in g.alive_players()[1:]:
                set_lynch_vote(g, p.user_id, True)
            resolve_lynch(g)
        assert g.players[0].alive is expect_alive


def test_secret_mode_never_reveals_the_role_of_the_hanged() -> None:
    g = build(["citizen", "citizen", "citizen", "mafia", "citizen"], pad=0, reveal=False)
    day_votes(g, {1: 0, 2: 0, 3: 0})
    resolve_votes(g)
    assert not g.players[0].alive and g.last_death_role is None


# --------------------------------------------------------------------------------------------
# 9. Win conditions x who is left alive
# --------------------------------------------------------------------------------------------

def _win(roles: list, *, snitch_hit: bool = False, arson_kills: int = 0):
    g = build(roles, pad=0)
    g.snitch_hit, g.arson_kills = snitch_hit, arson_kills
    return win_check(g)


WIN_TABLE = [
    # ------- nobody / one player
    ([], "draw"),
    (["citizen"], "town"), (["detective"], "town"), (["sergeant"], "town"), (["doctor"], "town"),
    (["lucky"], "town"), (["mayor"], "town"), (["hobo"], "town"), (["hooker"], "town"), (["kamikaze"], "town"),
    (["werewolf"], "town"),
    (["mafia"], "mafia"), (["don"], "mafia"), (["lawyer"], "mafia"), (["journalist"], "mafia"), (["killer"], "mafia"),
    ([("werewolf", {"faction": "mafia"})], "mafia"),
    (["maniac"], "maniac"), (["arsonist"], "arsonist"), (["mage"], "mage"), (["crook"], "crook"),
    disc("D13", ["suicide"], "town", id="lone-suicide-gives-the-town-the-win"),
    disc("D13", ["snitch"], None, id="lone-informer-nobody-wins"),
    # ------- mafia parity
    (["mafia", "citizen"], "mafia"), (["mafia", "citizen", "citizen"], None),
    (["mafia", "mafia", "citizen", "citizen"], "mafia"), (["mafia", "mafia", "citizen", "citizen", "citizen"], None),
    (["don", "mafia", "doctor", "detective", "citizen"], None), (["don", "mafia", "doctor", "detective"], "mafia"),
    (["mafia", "lawyer", "citizen", "citizen"], "mafia"), (["killer", "citizen"], "mafia"),
    (["mafia", "citizen", "sergeant"], None),
    # ------- neutrals count as opponents for the parity
    (["mafia", "maniac"], "mafia"), (["mafia", "maniac", "citizen"], None),
    (["mafia", "suicide"], "mafia"), (["mafia", "suicide", "citizen"], None),
    (["mafia", "arsonist"], "mafia"), (["mafia", "mage"], "mafia"), (["mafia", "crook"], "mafia"),
    (["mafia", "snitch"], "mafia"), (["mafia", "mafia", "maniac", "arsonist"], "mafia"),
    # ------- town wins only when nobody dangerous is left
    (["citizen", "citizen", "doctor"], "town"), (["citizen", "suicide"], "town"),
    (["citizen", "lucky", "mayor", "detective"], "town"),
    (["citizen", "maniac"], None), (["citizen", "arsonist"], None), (["citizen", "mage"], None),
    (["citizen", "crook"], None), (["citizen", "snitch"], None),
    (["citizen", "suicide", "maniac"], None),
    # ------- maniac
    (["maniac", "maniac"], "maniac"), (["maniac", "suicide"], "maniac"), (["maniac", "lucky"], None),
    (["maniac", "mage"], None), (["maniac", "snitch"], None), (["maniac", "arsonist"], None),
    # ------- lone wolves need to be alone
    (["arsonist", "mage"], None), (["mage", "crook"], None), (["crook", "snitch"], None),
    (["mage", "suicide"], None), (["arsonist", "suicide"], None),
    # ------- Traitor
    ([("werewolf", {"faction": "mafia"}), "citizen"], "mafia"),
    ([("werewolf", {"faction": "mafia"}), "citizen", "citizen"], None),
    (["mafia", "werewolf", "citizen"], None), (["mafia", "werewolf"], "mafia"),
    (["werewolf", "citizen", "doctor"], "town"),
]


def _win_cases():
    for row in WIN_TABLE:
        if hasattr(row, "values"):  # a pytest.param
            yield row
        else:
            roles, expected = row
            label = ",".join(r if isinstance(r, str) else f"{r[0]}*" for r in roles) or "nobody"
            yield pytest.param(roles, expected, id=f"{label}->{expected}")


@pytest.mark.parametrize(("roles", "expected"), list(_win_cases()))
def test_win_conditions_by_survivors(roles, expected) -> None:
    got = _win(roles)
    assert got == expected


def test_win_flags_beat_the_headcount() -> None:
    assert _win(["mafia", "citizen"], snitch_hit=True) == Winner.SNITCH
    assert _win([], snitch_hit=True) == Winner.SNITCH
    assert _win(["citizen", "citizen", "mafia"], arson_kills=3) == Winner.ARSONIST
    assert _win(["citizen"], arson_kills=2) == Winner.TOWN
    assert _win(["mafia", "citizen"], snitch_hit=True, arson_kills=3) == Winner.SNITCH


def _spec_winner(roles: list[str]) -> str | None:
    fac = [ROLE_FACTION[Role(r)].value for r in roles]
    m, t = fac.count("mafia"), fac.count("town")
    man, sui = roles.count("maniac"), roles.count("suicide")
    lone = {k: roles.count(k) for k in ("arsonist", "mage", "crook", "snitch")}
    extra = sum(lone.values())
    if not roles:
        return "draw"
    if len(roles) == 1 and roles[0] in ("arsonist", "mage", "crook"):
        return roles[0]
    if m == 0 and man == 0 and extra == 0:
        return "town"
    if man and m == 0 and t == 0 and extra == 0:
        return "maniac"
    if m and m >= t + man + sui + extra:
        return "mafia"
    return None


def test_every_survivor_combination_of_up_to_four_players_matches_the_rules() -> None:
    names = [r.value for r in Role]
    checked = 0
    for size in range(0, 5):
        for combo in itertools.combinations_with_replacement(names, size):
            assert _win(list(combo)) == _spec_winner(list(combo)), combo
            checked += 1
    assert checked > 10000


@pytest.mark.parametrize(
    ("kind", "winner"),
    [(Winner.TOWN, "town"), (Winner.MAFIA, "mafia"), (Winner.DRAW, "draw")],
)
def test_game_over_sets_phase_and_winner(kind, winner) -> None:
    roles = {"town": ["citizen"], "mafia": ["mafia"], "draw": []}[winner]
    g = build(roles, pad=0)
    assert win_check(g) == kind and g.winner == winner and g.phase == Phase.FINISHED


# Solo roles: how each one wins through real play ---------------------------------------------

def test_suicide_hanged_wins_immediately_even_with_the_town_alive() -> None:
    g = build(["suicide", "citizen", "citizen", "citizen", "mafia"], pad=0)
    day_votes(g, {1: 0, 2: 0, 3: 0})
    out = resolve_votes(g)
    assert out["winner"] == Winner.SUICIDE and g.phase == Phase.FINISHED


def test_suicide_killed_at_night_does_not_win() -> None:
    g = build(["suicide", "mafia", "citizen", "citizen", "citizen"], pad=0)
    out = night(g, (1, 0))
    assert out["winner"] is None and not g.players[0].alive


def test_mage_wins_as_the_last_one_alive_and_not_before() -> None:
    g = build(["mage", "mafia"], pad=0)
    out = night(g, (1, 0))
    assert not g.players[1].alive and out["winner"] == Winner.MAGE


def test_maniac_wins_when_the_last_other_is_a_suicide() -> None:
    g = build(["maniac", "citizen", "suicide"], pad=0)
    out = night(g, (0, 1))
    assert out["winner"] == Winner.MANIAC


# --------------------------------------------------------------------------------------------
# 10. Stalemate: 3 quiet rounds with at most 4 alive end the game in a draw
# --------------------------------------------------------------------------------------------

def _quiet(alive_n: int, **kw):
    g = build(["citizen"] * alive_n, pad=0)
    g.night_no = 1
    return g, kw


@pytest.mark.parametrize(
    ("alive_n", "calls", "draw_at"),
    [
        (4, 10, 3), (3, 10, 3), (2, 10, 3), (1, 10, 3),
        (5, 10, None), (6, 10, None), (12, 10, None),
    ],
)
def test_stalemate_boundaries_rounds_and_alive(alive_n: int, calls: int, draw_at: int | None) -> None:
    g, _ = _quiet(alive_n)
    first = None
    for i in range(1, calls + 1):
        if end_if_stalemate(g):
            first = i
            break
    assert first == draw_at
    if draw_at:
        assert g.winner == Winner.DRAW and g.phase == Phase.FINISHED and g.deadline is None


def test_stalemate_needs_three_full_quiet_rounds_not_two() -> None:
    g, _ = _quiet(4)
    assert not end_if_stalemate(g) and g.quiet_rounds == 1
    assert not end_if_stalemate(g) and g.quiet_rounds == 2
    assert end_if_stalemate(g) and g.quiet_rounds == 3


def test_a_death_resets_the_stalemate_counter() -> None:
    g, _ = _quiet(4)
    end_if_stalemate(g)
    end_if_stalemate(g)
    g.chronicle.append({"n": 1, "seat": 9, "cause": "night"})
    assert not end_if_stalemate(g) and g.quiet_rounds == 0
    assert not end_if_stalemate(g) and not end_if_stalemate(g)
    assert end_if_stalemate(g)


def test_fifth_player_alive_blocks_the_draw_and_the_fourth_allows_it() -> None:
    g, _ = _quiet(5)
    for _ in range(6):
        assert not end_if_stalemate(g)
    g.players[4].alive = False
    assert end_if_stalemate(g), "quiet rounds were counted all along; the 4th survivor unlocks the draw"


def test_the_very_first_call_before_night_one_does_not_count() -> None:
    g, _ = _quiet(4)
    g.night_no = 0
    assert not end_if_stalemate(g) and g.quiet_rounds == 0


def test_stalemate_limits_are_parameters() -> None:
    g, _ = _quiet(6)
    assert not end_if_stalemate(g, limit=1, max_alive=5)
    g2, _ = _quiet(5)
    assert end_if_stalemate(g2, limit=1, max_alive=5)


def test_kick_counts_as_a_death_for_the_stalemate() -> None:
    g = build(["citizen", "citizen", "citizen", "citizen", "mafia"], pad=0)
    g.night_no = 1
    end_if_stalemate(g)
    end_if_stalemate(g)
    kick(g, g.players[0].user_id)
    assert not end_if_stalemate(g) and g.quiet_rounds == 0


# --------------------------------------------------------------------------------------------
# 11. Dealing: who sits at the table at each size, modes and switched-off roles
# --------------------------------------------------------------------------------------------

UNLOCK = {
    "sergeant": 8, "hooker": 9, "maniac": 10, "lawyer": 11, "mayor": 12, "suicide": 13, "lucky": 14,
    "kamikaze": 15, "hobo": 16, "journalist": 17, "killer": 18, "werewolf": 19, "arsonist": 20, "mage": 21,
    "crook": 22, "snitch": 23,
}


@pytest.mark.parametrize("n", range(5, 24))
def test_classic_dealing_by_table_size(n: int) -> None:
    bag = bag_for(n)
    mafia = 1 if n <= 6 else 2 if n <= 8 else 3 if n <= 12 else 4 if n <= 17 else 5
    assert bag.total == n and len(bag.as_list()) == n
    assert (bag.mafia, bag.detective, bag.doctor) == (mafia, 1, 0 if n <= 6 else 1)
    assert bag.don == (1 if n >= 7 else 0)
    for role, threshold in UNLOCK.items():
        assert getattr(bag, role) == (1 if n >= threshold else 0), (n, role)
    assert (bag.citizen >= 1) == (n < 18), "plain citizens run out from 18 players"
    assert bag.as_list().count(Role.DON) == bag.don and bag.as_list().count(Role.MAFIA) == bag.mafia - bag.don


def test_below_five_players_there_is_no_game() -> None:
    with pytest.raises(ValueError):
        bag_for(4)


def test_the_21_roles_split_10_5_6_and_5_are_core() -> None:
    by = {f: [r for r in Role if ROLE_FACTION[r] == f] for f in Faction}
    assert (len(by[Faction.TOWN]), len(by[Faction.MAFIA]), len(by[Faction.NEUTRAL])) == (10, 5, 6)
    assert len(Role) == 21 and len(SPECIALS) == 16
    assert {r.value for r in Role} - set(SPECIALS) == {"citizen", "mafia", "don", "detective", "doctor"}


def test_night_roles_are_exactly_the_thirteen_with_a_button() -> None:
    assert {r.value for r in NIGHT_ROLES} == {
        "mafia", "don", "detective", "doctor", "maniac", "hooker", "lawyer", "hobo", "journalist", "killer",
        "arsonist", "crook", "snitch",
    }


@pytest.mark.parametrize("n", range(5, 24))
def test_switched_off_roles_become_citizens(n: int) -> None:
    bag = without(bag_for(n), list(SPECIALS))
    assert bag.total == n
    assert all(getattr(bag, r) == 0 for r in SPECIALS)


@pytest.mark.parametrize("n", range(5, 24))
def test_chaos_keeps_the_core_and_never_deals_a_disabled_role(n: int) -> None:
    import random

    classic = bag_for(n)
    for seed in range(8):
        bag = chaos_bag(n, random.Random(seed), ["maniac", "mage"])
        assert bag.total == n and bag.maniac == 0 and bag.mage == 0
        assert (bag.mafia, bag.don, bag.detective, bag.doctor) == (classic.mafia, classic.don, classic.detective, classic.doctor)
        if n < 10:
            assert bag.lawyer == bag.journalist == bag.killer == 0


# --------------------------------------------------------------------------------------------
# 12. Kick / bots (engine entry points the first simulator did not call)
# --------------------------------------------------------------------------------------------

def test_kick_mid_game_removes_the_action_and_the_votes() -> None:
    g = build(["mafia", "citizen", "citizen", "citizen", "citizen"], pad=0)
    act(g, 0, 1)
    done, winner = kick(g, g.players[0].user_id)
    assert done and winner == Winner.TOWN and g.phase == Phase.FINISHED
    assert g.chronicle[-1] == {"n": g.night_no, "seat": 1, "cause": "kick"}
    assert g.players[0].night_action is None and not g.players[0].alive


def test_kick_clears_the_votes_against_the_kicked_player() -> None:
    g = build(["citizen", "citizen", "citizen", "mafia", "mafia"], pad=0)
    resolve_night(g)
    day_votes(g, {1: 0, 2: 0, 3: 4})
    kick(g, g.players[0].user_id)
    assert g.players[1].vote is None and g.players[2].vote is None and g.players[3].vote == 5


def test_kick_the_detective_promotes_the_sergeant() -> None:
    g = build(["detective", "sergeant", "mafia", "citizen", "citizen"], pad=0)
    kick(g, g.players[0].user_id)
    assert g.players[1].role == "detective"


def test_kick_is_refused_for_the_dead_the_unknown_and_after_the_end() -> None:
    g = build(["citizen", "citizen", "mafia", "mafia", "citizen"], pad=0)
    g.players[0].alive = False
    assert kick(g, g.players[0].user_id) == (False, None)
    assert kick(g, 424242) == (False, None)
    g.phase = Phase.FINISHED
    assert kick(g, g.players[1].user_id) == (False, None)


def test_kick_in_the_lobby_is_leave_and_reseats() -> None:
    from tezmafia.engine import join, mark_dm_ok

    g = new_game(1, 1)
    for uid in (1, 2, 3):
        join(g, uid, f"P{uid}", None)
        mark_dm_ok(g, uid)
    assert kick(g, 2) == (True, None)
    assert [(p.user_id, p.seat) for p in g.players] == [(1, 1), (3, 2)]


def test_regression_a_kicked_accused_is_not_reported_as_hanged() -> None:
    """Fails without the fix: resolve_lynch reported the already-kicked accused as eliminated."""
    g = build(["citizen", "citizen", "citizen", "citizen", "mafia", "mafia"], pad=0)
    day_votes(g, {1: 0, 2: 0, 3: 0})
    begin_lynch(g, 1, 0, 60)
    kick(g, g.players[0].user_id)
    for p in g.alive_players()[:3]:
        set_lynch_vote(g, p.user_id, True)
    out = resolve_lynch(g)
    assert out["confirmed"] and out["eliminated"] is None
    assert sum(1 for ev in g.chronicle if ev["seat"] == 1) == 1


def test_regression_a_spent_pistol_clears_the_idle_count() -> None:
    """Fails without the fix: a Sergeant who skipped night 1, then fired, kept idle_nights=1 for good and
    could be removed a night early once promoted to Detective."""
    g = build([("sergeant", {"shop_gun": True}), "detective", "mafia"])
    resolve_night(g)
    assert g.players[0].idle_nights == 1
    begin_night(g, 0, 60)
    night(g, (0, 2), (1, 2))
    assert not g.players[0].shop_gun and g.players[0].idle_nights == 0


def test_bots_never_aim_at_their_own_faction_while_anyone_else_lives() -> None:
    import random

    from tezmafia.engine import add_bot, bot_lynch_votes, bot_night_moves, bot_votes, is_bot, join, mark_dm_ok, start

    for seed in range(60):
        rng = random.Random(seed)
        g = new_game(1, 1)
        join(g, 1, "Host", None)
        mark_dm_ok(g, 1)
        for _ in range(8):
            assert add_bot(g)[0]
        assert add_bot(g, "Robot")[1] in {"joined", "full"}
        start(g, rng)
        begin_night(g, 0, 60)
        g.night_no = 3
        bot_night_moves(g, rng)
        for p in g.alive_players():
            if is_bot(p.user_id) and p.night_action:
                tgt = g.by_seat(p.night_action)
                assert tgt.user_id != p.user_id
                if p.faction == "mafia":
                    assert tgt.faction != "mafia"
        g.phase = Phase.DAY
        begin_voting(g, 0, 60)
        bot_votes(g, rng)
        for p in g.alive_players():
            if is_bot(p.user_id) and p.vote and p.faction == "mafia":
                assert g.by_seat(p.vote).faction != "mafia"
        accused = next(p for p in g.alive_players() if p.faction == "mafia")
        begin_lynch(g, accused.seat, 0, 60)
        bot_lynch_votes(g, rng)
        for p in g.alive_players():
            if is_bot(p.user_id) and p.faction == "mafia":
                assert p.lynch_yes is False or p.user_id == accused.user_id


def test_bot_ids_are_negative_unique_and_not_counted_as_humans() -> None:
    from tezmafia.engine import add_bot, humans, is_bot, join

    g = new_game(1, 1)
    join(g, 1, "Host", None)
    for _ in range(4):
        add_bot(g)
    assert [p.user_id for p in g.players] == [1, -1, -2, -3, -4]
    assert [p.user_id for p in humans(g)] == [1]
    assert all(is_bot(p.user_id) for p in g.players[1:]) and all(p.dm_ok for p in g.players[1:])


def test_add_bot_stops_at_the_table_limit_and_outside_the_lobby() -> None:
    from tezmafia.engine import add_bot

    g = new_game(1, 1, max_players=3)
    assert [add_bot(g)[1] for _ in range(4)] == ["joined", "joined", "joined", "full"]
    g.phase = Phase.NIGHT
    assert add_bot(g) == (False, "not_lobby")


def test_tables_with_bots_play_to_the_end() -> None:
    """Bots at the table (up to all seats but the host's): every game ends, with no rule violation."""
    from scripts.loadtest.sim import play

    for seed in range(40):
        res = play(seed, n=5 + seed % 10, extras=True)
        assert not res.violations and not res.stalled, (seed, res.violations)


def test_the_extended_simulator_catches_a_planted_engine_bug(monkeypatch) -> None:
    """Negative test: if kick stopped clearing votes the simulator must say so."""
    from scripts.loadtest import sim
    from tezmafia import engine

    real = engine.kick

    def broken(game, user_id):
        player = game.by_user(user_id)
        votes = {p.user_id: p.vote for p in game.players}
        done, winner = real(game, user_id)
        if done and player:
            for p in game.players:
                if votes[p.user_id] == player.seat:
                    p.vote = player.seat  # the bug: votes against the kicked player survive
        return done, winner

    monkeypatch.setattr(sim, "kick", broken)
    seen = []
    for seed in range(400):
        seen += sim.play(seed, extras=True).violations
    assert any("votes against the kicked player were not cleared" in v for v in seen)


# --------------------------------------------------------------------------------------------
# 13. More documented discrepancies (behaviour asserted as it is today)
# --------------------------------------------------------------------------------------------

@D
def test_D11_a_kicked_player_on_the_winning_side_is_still_counted_as_a_winner() -> None:
    """kick() removes the player like a death; record_stats() pays `player_won`, which only looks at the
    faction/role, so a kicked mafioso (or Informer, Suicide...) shares the win. Kick sets no last_death_*."""
    from tezmafia.engine import player_won

    g = build(["mafia", "mafia", "citizen", "citizen", "citizen"], pad=0)
    kick(g, g.players[0].user_id)
    g.winner = Winner.MAFIA
    assert player_won(g, g.players[0]) is True and g.last_death_seat is None


@D
def test_D23_the_doctor_cannot_stop_fire() -> None:
    """Texts only say the Executioner ignores protection; the Arsonist's fire does too."""
    g = build(["arsonist", "doctor", "citizen"], marks=(1,))
    night(g, (0, 0), (1, 1))
    assert not g.players[1].alive and g.arson_kills == 1
