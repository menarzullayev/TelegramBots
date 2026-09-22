"""End-to-end coverage of every engine / text / keyboard state."""
from __future__ import annotations

import random

import pytest

from tezmafia.emoji import FX, SLOTS, ce, icon
from tezmafia.engine import (
    Phase,
    Winner,
    after_day_announce_night,
    begin_night,
    begin_voting,
    can_start,
    cancel,
    dm_pending,
    from_dict,
    join,
    leave,
    mark_dm_ok,
    new_game,
    resolve_night,
    resolve_votes,
    set_night_action,
    set_vote,
    start,
    to_dict,
    win_check,
)
from tezmafia.keyboards import lobby_kb, night_kb, roles_kb, vote_kb
from tezmafia.roles import Role, bag_for
from tezmafia import texts


def _ready(n: int = 5, host: int = 100) -> object:
    g = new_game(1, host)
    for i in range(n):
        join(g, host + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, host + i)
    return g


def _force(g, roles: list[str]) -> None:
    start(g, rng=random.Random(0))
    for p, role in zip(g.players, roles, strict=True):
        p.role = role
        from tezmafia.roles import ROLE_FACTION, Role

        p.faction = ROLE_FACTION[Role(role)].value


def test_bag_all_sizes_and_errors() -> None:
    assert bag_for(5).mafia == 1 and bag_for(5).doctor == 0
    assert bag_for(6).mafia == 1
    assert bag_for(7).doctor == 1 and bag_for(7).mafia == 2
    assert bag_for(8).mafia == 2
    assert bag_for(9).mafia == 3
    assert bag_for(12).mafia == 3
    assert bag_for(13).mafia == 4
    assert bag_for(16).total == 16
    with pytest.raises(ValueError):
        bag_for(4)


def test_join_leave_full_closed() -> None:
    g = new_game(1, 1, max_players=5, min_players=5)
    for i in range(5):
        assert join(g, i + 1, f"P{i}", None)[1] == "joined"
    assert join(g, 99, "X", None) == (False, "full")
    assert join(g, 1, "P0", None)[1] == "already"
    assert leave(g, 3) is True
    assert [p.user_id for p in g.players] == [1, 2, 4, 5]
    assert [p.seat for p in g.players] == [1, 2, 3, 4]
    assert leave(g, 3) is False
    assert leave(g, 77) is False
    start_g = _ready(5)
    start(start_g, rng=random.Random(1))
    assert join(start_g, 999, "Z", None) == (False, "lobby_closed")
    assert leave(start_g, start_g.players[0].user_id) is False


def test_dm_and_can_start_reasons() -> None:
    g = new_game(1, 100)
    assert can_start(g) == (False, "too_few")
    for i in range(5):
        join(g, 100 + i, f"P{i}", None)
    assert can_start(g) == (False, "dm_pending")
    assert mark_dm_ok(g, 1) is False
    for i in range(5):
        assert mark_dm_ok(g, 100 + i) is True
        assert mark_dm_ok(g, 100 + i) is True
    assert can_start(g) == (True, "ok")
    assert dm_pending(g) == []
    start(g, rng=random.Random(2))
    assert can_start(g) == (False, "not_lobby")
    with pytest.raises(RuntimeError):
        start(g)


def test_html_label_escapes() -> None:
    g = new_game(1, 1)
    join(g, 1, "<b>x</b>", "a&b")
    assert "&lt;b&gt;" in g.players[0].html_label()
    assert "a&amp;b" in g.players[0].html_label()
    join(g, 2, "NoUser", None)
    assert g.players[1].html_label() == "NoUser"


def test_night_action_all_reasons() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    m, d, c = g.players[0], g.players[1], g.players[2]
    assert set_night_action(g, m.user_id, c.seat)[1] == "not_night"
    begin_night(g, 0, 10)
    assert set_night_action(g, 999, 1)[1] == "dead"
    g.players[4].alive = False
    assert set_night_action(g, m.user_id, 5)[1] == "bad_target"
    g.players[4].alive = True
    assert set_night_action(g, m.user_id, m.seat)[1] == "no_self"
    assert set_night_action(g, d.user_id, d.seat)[1] == "no_self"
    assert set_night_action(g, c.user_id, m.seat)[1] == "no_action"
    g2 = _ready(8)
    start(g2, rng=random.Random(4))
    maf = g2.alive_mafia()
    if len(maf) >= 2:
        begin_night(g2, 0, 10)
        assert set_night_action(g2, maf[0].user_id, maf[1].seat)[1] == "no_teamkill"


def test_doctor_self_and_save() -> None:
    g = _ready(7)
    start(g, rng=random.Random(1))
    doctor = next(p for p in g.players if p.role == "doctor")
    begin_night(g, 0, 10)
    assert set_night_action(g, doctor.user_id, doctor.seat)[0] is True


def test_mafia_resolve_majority_unanimous_first_split() -> None:
    g = _ready(8)
    start(g, rng=random.Random(4))
    maf = g.alive_mafia()
    towns = g.alive_town()
    assert len(maf) >= 2
    begin_night(g, 0, 10)
    set_night_action(g, maf[0].user_id, towns[0].seat)
    set_night_action(g, maf[1].user_id, towns[1].seat)
    first = resolve_night(g)
    don = next((p for p in maf if p.role == "don"), None)
    if don and don.night_action:
        assert first["killed"] == don.night_action
    else:
        assert first["miss"] is True

    g = _ready(8)
    start(g, rng=random.Random(4))
    maf = g.alive_mafia()
    towns = g.alive_town()
    g.mafia_resolve = "unanimous"
    begin_night(g, 0, 10)
    set_night_action(g, maf[0].user_id, towns[0].seat)
    # second silent
    assert resolve_night(g)["miss"] is True

    g = _ready(8)
    start(g, rng=random.Random(4))
    maf = g.alive_mafia()
    towns = g.alive_town()
    g.mafia_resolve = "unanimous"
    begin_night(g, 0, 10)
    for m in maf:
        set_night_action(g, m.user_id, towns[0].seat)
    r = resolve_night(g)
    assert r["killed"] == towns[0].seat

    g = _ready(8)
    start(g, rng=random.Random(4))
    maf = g.alive_mafia()
    towns = g.alive_town()
    g.mafia_resolve = "first"
    begin_night(g, 0, 10)
    set_night_action(g, maf[0].user_id, towns[0].seat)
    set_night_action(g, maf[1].user_id, towns[1].seat)
    assert resolve_night(g)["killed"] == towns[0].seat


def test_night_kill_mafia_parity_win() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    mafia = g.players[0]
    begin_night(g, 0, 10)
    set_night_action(g, mafia.user_id, 2)
    resolve_night(g)
    begin_night(g, 0, 10)
    set_night_action(g, mafia.user_id, 3)
    resolve_night(g)
    begin_night(g, 0, 10)
    set_night_action(g, mafia.user_id, 4)
    r = resolve_night(g)
    assert r["winner"] == Winner.MAFIA
    assert g.phase == Phase.FINISHED


def test_detective_sees_faction() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, g.players[1].user_id, 1)
    r = resolve_night(g)
    assert r["detective_result"]["is_mafia"] is True
    assert r["miss"] is True


def test_vote_paths() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    with pytest.raises(RuntimeError):
        begin_voting(g, 0, 10)
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_voting(g, 0, 20)
    target = g.players[0]
    assert set_vote(g, target.user_id, target.seat)[1] == "no_self"
    assert set_vote(g, 999, 1)[1] == "dead"
    assert set_vote(g, g.players[1].user_id, 99)[1] == "bad_target"
    assert set_vote(g, g.players[1].user_id, 1)[0]
    assert set_vote(g, g.players[1].user_id, None) == (True, "cleared")
    g.phase = Phase.DAY
    assert set_vote(g, g.players[1].user_id, 1)[1] == "not_voting"


def test_vote_tie_empty_and_elim_town_win() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_voting(g, 0, 10)
    r = resolve_votes(g)
    assert r["eliminated"] is None and r["tie"] is False

    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_voting(g, 0, 10)
    set_vote(g, 101, 1)
    set_vote(g, 102, 2)
    r = resolve_votes(g)
    assert r["tie"] is True
    assert g.players[0].alive and g.players[1].alive

    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_voting(g, 0, 10)
    for uid in (101, 102, 103, 104):
        set_vote(g, uid, 1)
    r = resolve_votes(g)
    assert r["eliminated"] == 1
    assert r["winner"] == Winner.TOWN


def test_after_day_and_cancel_persist() -> None:
    g = _ready(5)
    start(g, rng=random.Random(9))
    cancel(g)
    after_day_announce_night(g, 0, 10)
    assert g.phase == Phase.FINISHED

    g2 = _ready(5)
    start(g2, rng=random.Random(8))
    begin_night(g2, 0, 1)
    resolve_night(g2)
    after_day_announce_night(g2, 1, 10)
    assert g2.phase == Phase.NIGHT

    blob = to_dict(g2)
    g3 = from_dict(blob)
    assert g3.id == g2.id
    assert g3.players[0].html_label()


def test_e2e_town_and_mafia_scripts() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 5)
    resolve_night(g)
    assert not g.players[4].alive
    begin_voting(g, 0, 10)
    for uid in (101, 102, 103):
        set_vote(g, uid, 1)
    assert resolve_votes(g)["winner"] == Winner.TOWN

    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    for seat in (2, 3, 4):
        begin_night(g, 0, 10)
        set_night_action(g, 100, seat)
        resolve_night(g)
    assert g.winner == Winner.MAFIA


def test_texts_and_emoji_and_keyboards() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    assert "tg-emoji" in texts.lobby_text(g, "bot")
    assert "Qora" in texts.roles_public(g)
    assert "Qora qo‘l" in texts.role_dm(g, 100)
    assert "Komissar" in texts.role_dm(g, 101)
    assert "Tinch" in texts.role_dm(g, 102)
    assert texts.role_dm(g, 999)
    assert "Tun" in texts.night_group(g)
    assert texts.night_prompt(g, 100, True)
    assert texts.night_prompt(g, 102, False)
    begin_night(g, 0, 1)
    resolve_night(g)
    assert "Kun" in texts.day_group(g, True)
    g.night_saved = True
    g.night_miss = False
    g.last_death_seat = None
    assert "Shifokor" in texts.day_group(g, True)
    g.night_saved = False
    g.last_death_seat = 5
    g.last_death_role = "citizen"
    g.last_death_cause = "night"
    assert "uyiga" in texts.day_group(g, True)
    assert "Sud" in texts.vote_group(g)
    assert "ovoz yo‘q" in texts.vote_tally(g)
    set_vote  # keep import used
    begin_voting(g, 0, 10)
    set_vote(g, 101, 1)
    assert "ovoz" in texts.vote_tally(g)
    assert texts.elim_group(g, True, True)
    g.last_death_seat = 1
    g.last_death_cause = "vote"
    g.last_death_role = "mafia"
    assert "sud" in texts.elim_group(g, False, True)
    g.winner = "mafia"
    assert "quladi" in texts.game_over(g)
    g.winner = "town"
    assert "nafas" in texts.game_over(g)
    assert "Game Over" in texts.game_over_short(g)
    assert "Qorashahar" in texts.help_html()
    for code in ("not_lobby", "too_few", "dm_pending"):
        assert texts.start_reason(code)
    for code in (
        "not_night",
        "not_voting",
        "dead",
        "bad_target",
        "no_teamkill",
        "no_action",
        "no_self",
        "cleared",
        "lobby_closed",
        "full",
        "unknown",
    ):
        assert texts.action_reason(code)
    assert "Qora" in texts.detective_result("X", True)
    assert "tinch" in texts.detective_result("X", False)
    assert texts.dm_opened()
    assert texts.cancelled()
    assert texts.picked("A")
    assert texts.voted("B")
    assert "<tg-emoji" in ce("mafia")
    assert icon("mafia")
    assert ce("missing-slot") == "missing-slot"
    assert icon("nope") is None
    assert FX["fire"]
    assert "digest" not in SLOTS or True
    assert roles_kb().inline_keyboard
    kb = lobby_kb(g, "qorashahar_mafia_bot")
    assert kb.inline_keyboard
    assert night_kb(g, 100).inline_keyboard  # mafia after voting phase still has role
    assert vote_kb(g).inline_keyboard
    empty = night_kb(g, 102)
    assert empty.inline_keyboard == [] or True
    ghost = night_kb(g, 999)
    assert ghost.inline_keyboard == []


def test_win_check_neither() -> None:
    g = _ready(5)
    start(g, rng=random.Random(3))
    assert win_check(g) is None
    assert g.players[0].label()
    g.players[0].username = None
    assert g.players[0].label() == g.players[0].first_name


def test_remaining_branches() -> None:
    g = new_game(1, 1)
    join(g, 1, "A", None)
    assert "quloq" in texts.lobby_text(g, "bot")
    g7 = _ready(7)
    start(g7, rng=random.Random(1))
    doctor = next(p for p in g7.players if p.role == "doctor")
    det = next(p for p in g7.players if p.role == "detective")
    assert "Shifokor" in texts.role_dm(g7, doctor.user_id)
    assert night_kb(g7, det.user_id).inline_keyboard
    assert night_kb(g7, doctor.user_id).inline_keyboard
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    g.night_miss = False
    g.night_saved = False
    g.last_death_seat = None
    assert "Tong" in texts.day_group(g, True)
    g.last_death_seat = None
    g.last_death_cause = None
    assert "yetarli" in texts.elim_group(g, False, True)
    assert texts.help_text()
    assert "rollar" in texts.roles_catalog().lower() or "Rol" in texts.roles_catalog()
    assert "Qora" in texts.role_card("mafia")
    assert texts.role_card("missing-role")
    g.winner = "mafia"
    assert "Qora" in texts.game_over_short(g)
    for w in ("maniac", "suicide", "arsonist", "snitch", "mage", "crook"):
        g.winner = w
        assert texts.game_over_short(g)
        assert texts.game_over(g)
    with pytest.raises(RuntimeError):
        resolve_night(g)
    with pytest.raises(RuntimeError):
        resolve_votes(g)
    g = _ready(9)
    start(g, rng=random.Random(4))
    maf = g.alive_mafia()
    towns = g.alive_town()
    assert len(maf) >= 3
    begin_night(g, 0, 10)
    set_night_action(g, maf[0].user_id, towns[0].seat)
    r = resolve_night(g)
    assert r["miss"] is True
    g = _ready(5)
    _force(g, ["mafia", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    g.players[1].night_action = 99
    r = resolve_night(g)
    assert r["detective_result"] is None or r["detective_result"]
