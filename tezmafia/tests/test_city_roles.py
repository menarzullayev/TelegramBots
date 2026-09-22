from __future__ import annotations

import random

from tezmafia.engine import (
    Phase,
    Winner,
    begin_lynch,
    begin_night,
    begin_voting,
    extend_lobby,
    from_dict,
    join,
    mark_dm_ok,
    new_game,
    peek_votes,
    resolve_lynch,
    resolve_night,
    resolve_votes,
    set_lynch_vote,
    set_night_action,
    set_vote,
    start,
    to_dict,
    win_check,
)
from tezmafia.keyboards import lang_kb, lynch_kb, night_kb
from tezmafia.roles import ROLE_FACTION, Role, bag_for
from tezmafia import texts


def _ready(n: int = 5) -> object:
    g = new_game(1, 100)
    for i in range(n):
        join(g, 100 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, 100 + i)
    return g


def _force(g, roles: list[str]) -> None:
    start(g, rng=random.Random(0))
    for p, role in zip(g.players, roles, strict=True):
        p.role = role
        p.faction = ROLE_FACTION[Role(role)].value


def test_bag_extras_and_public() -> None:
    b8 = bag_for(8)
    assert b8.don == 1 and b8.sergeant == 1 and b8.total == 8
    b16 = bag_for(16)
    assert b16.total == 16
    assert b16.citizen >= 1
    assert b16.as_list()
    assert bag_for(12).public_counts()


def test_don_looks_town_and_breaks_tie() -> None:
    g = _ready(5)
    _force(g, ["don", "detective", "citizen", "citizen", "mafia"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 3)
    set_night_action(g, 104, 4)
    set_night_action(g, 101, 1)
    r = resolve_night(g)
    assert r["detective_result"]["is_mafia"] is False
    assert r["killed"] == 3


def test_hooker_blocks_and_vote() -> None:
    g = _ready(5)
    _force(g, ["mafia", "hooker", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 3)
    set_night_action(g, 101, 1)
    r = resolve_night(g)
    assert r["miss"] is True
    assert g.players[0].blocked is True
    begin_voting(g, 0, 10)
    assert set_vote(g, 100, 3)[1] == "blocked"


def test_lawyer_covers_and_doctor_self_once() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "lawyer", "doctor", "citizen"])
    begin_night(g, 0, 10)
    assert set_night_action(g, 103, 4)[0]
    set_night_action(g, 102, 1)
    set_night_action(g, 101, 1)
    r = resolve_night(g)
    assert r["detective_result"]["is_mafia"] is False
    assert g.lawyer_cover == 1
    begin_voting(g, 0, 10)
    for uid in (101, 103, 104):
        set_vote(g, uid, 1)
    assert resolve_votes(g)["eliminated"] is None
    begin_night(g, 0, 10)
    assert set_night_action(g, 103, 4)[1] == "self_used"


def test_lucky_kamikaze_hobo_maniac_suicide() -> None:
    g = _ready(5)
    _force(g, ["mafia", "lucky", "kamikaze", "hobo", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    r = resolve_night(g)
    assert r["killed"] is None
    assert g.players[1].alive and g.players[1].lucky_used

    g = _ready(5)
    _force(g, ["mafia", "kamikaze", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert not g.players[1].alive
    assert not g.players[0].alive

    g = _ready(5)
    _force(g, ["mafia", "hobo", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 101, 3)
    set_night_action(g, 100, 2)
    r = resolve_night(g)
    assert r["miss"] is True
    assert g.players[1].alive

    g = _ready(5)
    _force(g, ["maniac", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert not g.players[1].alive

    g = _ready(5)
    _force(g, ["maniac", "citizen", "citizen", "citizen", "citizen"])
    for p in g.players[1:]:
        p.alive = False
    assert win_check(g) == Winner.MANIAC

    g = _ready(5)
    _force(g, ["suicide", "mafia", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_voting(g, 0, 10)
    for uid in (101, 102, 103, 104):
        set_vote(g, uid, 1)
    assert resolve_votes(g)["winner"] == Winner.SUICIDE


def test_sergeant_mayor_lynch_extend() -> None:
    g = _ready(5)
    _force(g, ["mafia", "detective", "sergeant", "citizen", "citizen"])
    g.players[1].alive = False
    begin_night(g, 0, 10)
    resolve_night(g)
    assert g.players[2].role == "detective"

    g = _ready(5)
    _force(g, ["mafia", "mayor", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_voting(g, 0, 10)
    set_vote(g, 101, 1)
    set_vote(g, 102, 3)
    seat, tie, tally = peek_votes(g)
    assert seat == 1 and not tie and tally[1] == 2

    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_lynch(g, 1, 0, 10)
    assert set_lynch_vote(g, 100, True)[1] == "no_self"
    assert set_lynch_vote(g, 101, True)[0]
    assert set_lynch_vote(g, 102, True)[0]
    assert set_lynch_vote(g, 103, False)[0]
    r = resolve_lynch(g)
    assert r["confirmed"] and r["winner"] == Winner.TOWN

    g = new_game(1, 1)
    assert extend_lobby(g, 30)[0]
    assert extend_lobby(g, 30, max_extends=1)[1] == "no_extend"
    start(_ready(5), rng=random.Random(1))
    live = _ready(5)
    start(live, rng=random.Random(1))
    assert extend_lobby(live, 10)[1] == "not_lobby"
    blob = to_dict(live)
    assert from_dict(blob).id == live.id
    assert night_kb(live, live.players[0].user_id)
    assert lynch_kb(live).inline_keyboard
    assert lang_kb().inline_keyboard
    from tezmafia.i18n import LANGS
    from tezmafia.keyboards import chats_kb, host_kb

    assert len(lang_kb().inline_keyboard) == len(LANGS)
    en_label = LANGS["en"]
    uz_label = LANGS["uz"]
    en_kb = lang_kb("en")
    for row in en_kb.inline_keyboard:
        for b in row:
            if b.text == en_label:
                assert b.style == "primary"
            elif b.text == uz_label:
                assert not b.style
    host = host_kb("qorashahar_mafia_bot")
    host_labels = [b.text for row in host.inline_keyboard for b in row]
    assert "Stolga kirish" in host_labels
    assert any(b.url and "startgroup" in (b.url or "") for row in host.inline_keyboard for b in row)
    chats = chats_kb([live], "qorashahar_mafia_bot")
    assert chats.inline_keyboard
    assert texts.host_menu_text()
    assert texts.chats_text(0)
    assert texts.chats_text(1)
    assert "Manyak" in texts.role_dm(live, live.players[0].user_id) or texts.role_dm(live, live.players[0].user_id)
    live.winner = "maniac"
    assert "Manyak" in texts.game_over(live)
    live.winner = "suicide"
    assert "qasd" in texts.game_over_short(live)
    assert texts.lynch_text(live)
    assert texts.profile_text("A", 1, 1)
    assert texts.top_text([])
    assert texts.top_text([("A", 2, 1)])
    assert texts.settings_text("uz")
    assert texts.lang_switched("ru")
    assert texts.extended(90)
    assert texts.next_phase()
    for role in Role:
        g2 = _ready(5)
        roles = [role.value, "citizen", "citizen", "citizen", "citizen"]
        if role == Role.CITIZEN:
            roles[0] = "citizen"
        _force(g2, roles)
        assert texts.role_dm(g2, 100)
        assert night_kb(g2, 100)


def test_az_roles_and_detective_shoot() -> None:
    b20 = bag_for(20)
    assert b20.total == 20 and b20.journalist == 1 and b20.arsonist == 1
    assert bag_for(23).snitch == 1

    g = _ready(5)
    _force(g, ["detective", "citizen", "citizen", "citizen", "mafia"])
    begin_night(g, 0, 10)
    assert g.round == 1
    assert set_night_action(g, 100, 2, kind="shoot") == (False, "no_first_shoot")
    assert g.players[0].night_action is None
    kb1 = night_kb(g, 100)
    assert not any("🔫" in (b.text or "") for row in kb1.inline_keyboard for b in row)
    begin_night(g, 0, 10)
    assert set_night_action(g, 100, 2, kind="shoot")[0]
    r = resolve_night(g)
    assert r["killed"] == 2
    assert not g.players[1].alive

    g = _ready(5)
    _force(g, ["killer", "detective", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert not g.players[0].alive
    assert g.players[1].alive

    g = _ready(5)
    _force(g, ["killer", "doctor", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 3)
    set_night_action(g, 101, 3)
    resolve_night(g)
    assert not g.players[2].alive

    g = _ready(5)
    _force(g, ["mafia", "werewolf", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert g.players[1].alive
    assert g.players[1].faction == "mafia"

    g = _ready(5)
    _force(g, ["mafia", "mage", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert g.players[1].alive
    assert not g.players[0].alive

    g = _ready(5)
    _force(g, ["arsonist", "citizen", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    begin_night(g, 0, 10)
    set_night_action(g, 100, 3)
    resolve_night(g)
    begin_night(g, 0, 10)
    set_night_action(g, 100, 4)
    resolve_night(g)
    begin_night(g, 0, 10)
    set_night_action(g, 100, 1)
    r = resolve_night(g)
    assert r["winner"] == Winner.ARSONIST

    g = _ready(5)
    _force(g, ["snitch", "detective", "citizen", "citizen", "mafia"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 3)
    set_night_action(g, 101, 3)
    r = resolve_night(g)
    assert r["winner"] == Winner.SNITCH

    g = _ready(5)
    _force(g, ["crook", "citizen", "citizen", "citizen", "mafia"])
    begin_night(g, 0, 1)
    set_night_action(g, 100, 2)
    resolve_night(g)
    begin_voting(g, 0, 10)
    set_vote(g, 100, 5)
    set_vote(g, 102, 1)
    seat, _tie, tally = peek_votes(g)
    assert g.players[1].vote == 5
    assert tally.get(5, 0) >= 2

    g = _ready(5)
    _force(g, ["journalist", "doctor", "citizen", "citizen", "mafia"])
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    set_night_action(g, 101, 3)
    r = resolve_night(g)
    assert r["journalist_result"]["helper"] is True
    assert texts.journalist_result("A", ["B"], True)

    g = _ready(5)
    _force(g, ["mage", "citizen", "citizen", "citizen", "citizen"])
    for p in g.players[1:]:
        p.alive = False
    assert win_check(g) == Winner.MAGE
    g = _ready(5)
    _force(g, ["crook", "citizen", "citizen", "citizen", "citizen"])
    for p in g.players[1:]:
        p.alive = False
    assert win_check(g) == Winner.CROOK
    g.winner = "arsonist"
    assert "yondi" in texts.game_over(g)
    g.winner = "snitch"
    assert "Xufiya" in texts.game_over_short(g)


def test_afk_two_nights_kills_night_roles() -> None:
    g = _ready(5)
    _force(g, ["don", "doctor", "detective", "citizen", "citizen"])
    begin_night(g, 0, 1)
    r1 = resolve_night(g)
    assert r1["afk"] == []
    assert all(p.alive for p in g.players)
    assert g.players[0].idle_nights == 1
    begin_night(g, 0, 1)
    r2 = resolve_night(g)
    assert set(r2["afk"]) == {1, 2, 3}
    assert not g.players[0].alive
    assert g.players[3].alive
    assert r2["winner"] == Winner.TOWN
    assert "uxlamay" in texts.last_words(g, r2["afk"])
    assert "uxlamay" in texts.day_group(g, True)
    assert "uxlamay" in texts.game_over(g)


def test_afk_resets_when_night_role_acts() -> None:
    g = _ready(5)
    _force(g, ["don", "doctor", "citizen", "citizen", "citizen"])
    begin_night(g, 0, 1)
    resolve_night(g)
    begin_night(g, 0, 1)
    assert set_night_action(g, 100, 5)[0]
    r = resolve_night(g)
    assert g.players[0].idle_nights == 0
    assert g.players[0].alive
    assert 1 not in r["afk"]
    blob = to_dict(g)
    for p in blob["players"]:
        p.pop("idle_nights", None)
    blob.pop("afk_deaths", None)
    restored = from_dict(blob)
    assert restored.players[0].idle_nights == 0
    assert restored.afk_deaths == []


def test_shop_items_and_detective_n1() -> None:
    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    g.players[1].shop_shield = True
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert g.players[1].alive
    assert not g.players[1].shop_shield

    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    g.players[1].shop_vote_shield = True
    g.phase = Phase.DAY
    begin_voting(g, 0, 10)
    for uid in (100, 102, 103, 104):
        set_vote(g, uid, 2)
    r = resolve_votes(g)
    assert r["eliminated"] is None
    assert g.players[1].alive
    assert not g.players[1].shop_vote_shield

    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    g.players[1].shop_vote_shield = True
    begin_lynch(g, 2, 0, 10)
    for uid in (100, 102, 103, 104):
        set_lynch_vote(g, uid, True)
    lr = resolve_lynch(g)
    assert lr["eliminated"] is None
    assert g.players[1].alive

    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    g.players[1].shop_mask = True
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert not g.players[1].alive
    assert g.last_death_role is None
    assert 2 in g.masked_deaths
    assert "Tinch" not in texts.last_words(g, [2])

    g = _ready(5)
    _force(g, ["detective", "mafia", "citizen", "citizen", "citizen"])
    g.players[1].shop_fake_id = True
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert g.detective_result and g.detective_result["is_mafia"] is False

    g = _ready(5)
    _force(g, ["killer", "citizen", "citizen", "citizen", "citizen"])
    g.players[1].shop_killer_shield = True
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert g.players[1].alive
    assert not g.players[1].shop_killer_shield

    g = _ready(5)
    _force(g, ["mafia", "citizen", "citizen", "citizen", "citizen"])
    g.players[1].shop_killer_shield = True
    begin_night(g, 0, 10)
    set_night_action(g, 100, 2)
    resolve_night(g)
    assert not g.players[1].alive

    g = _ready(5)
    _force(g, ["citizen", "citizen", "citizen", "citizen", "mafia"])
    g.players[0].shop_gun = True
    begin_night(g, 0, 10)
    assert night_kb(g, 100).inline_keyboard
    assert set_night_action(g, 100, 5)[0]
    resolve_night(g)
    assert not g.players[4].alive
    assert not g.players[0].shop_gun

    blob = to_dict(g)
    for p in blob["players"]:
        p.pop("shop_shield", None)
        p.pop("shop_vote_shield", None)
        p.pop("shop_mask", None)
        p.pop("shop_fake_id", None)
        p.pop("shop_gun", None)
    restored = from_dict(blob)
    assert restored.players[0].shop_shield is False
    assert "Dollar" in texts.profile_text("A", 1, 1, 35, 1, {"shield": 1})
    assert "himoya" in texts.shop_text(10, 0, {}).lower() or "Himoya" in texts.shop_text(10, 0, {})
    assert "Qotildan" in texts.shop_text(10, 0, {})
    assert "tekshiruv" in texts.action_reason("no_first_shoot")
    from tezmafia.shop import resolve_item, resolve_role

    assert resolve_item("maska") == "mask"
    assert resolve_item("qotil") == "killer_shield"
    assert resolve_item("yoq") is None
    assert resolve_role("komissar") == "detective"
    assert resolve_role("detective") == "detective"
    from tezmafia.roles import ROLE_UZ, Role

    assert resolve_role(ROLE_UZ[Role.DOCTOR]) == "doctor"
    assert resolve_role("???") is None
    assert "Keyingi rol" in texts.profile_text("A", 1, 1, 0, 0, {}, "detective")
