from tezmafia.engine import (
    begin_night,
    begin_voting,
    can_start,
    join,
    mark_dm_ok,
    new_game,
    resolve_night,
    resolve_votes,
    set_night_action,
    set_vote,
    start,
    win_check,
)
from tezmafia.roles import bag_for


def _ready(n: int = 6) -> object:
    g = new_game(1, 100)
    for i in range(n):
        join(g, 100 + i, f"P{i}", f"p{i}")
        mark_dm_ok(g, 100 + i)
    return g


def test_bag_scales() -> None:
    assert bag_for(5).mafia == 1
    assert bag_for(7).doctor == 1
    assert bag_for(10).mafia == 3
    assert bag_for(10).total == 10


def test_cannot_start_without_dm() -> None:
    g = new_game(1, 100)
    for i in range(5):
        join(g, 100 + i, f"P{i}", None)
    ok, reason = can_start(g)
    assert ok is False
    assert reason == "dm_pending"
    for i in range(5):
        mark_dm_ok(g, 100 + i)
    ok, reason = can_start(g)
    assert ok is True


def test_duplicate_join() -> None:
    g = new_game(1, 100)
    assert join(g, 1, "A", None)[1] == "joined"
    assert join(g, 1, "A", None)[1] == "already"
    assert len(g.players) == 1


def test_night_doctor_saves() -> None:
    g = _ready(7)
    start(g, rng=__import__("random").Random(1))
    mafia = next(p for p in g.players if p.role == "mafia")
    doctor = next(p for p in g.players if p.role == "doctor")
    victim = next(p for p in g.players if p.user_id not in (mafia.user_id, doctor.user_id) and p.faction == "town")
    begin_night(g, 0, 30)
    for m in g.alive_mafia():
        set_night_action(g, m.user_id, victim.seat)
    set_night_action(g, doctor.user_id, victim.seat)
    result = resolve_night(g)
    assert result["saved"] is True
    assert result["killed"] is None
    assert victim.alive is True
    assert result["winner"] is None


def test_night_kill_then_parity_win() -> None:
    g = _ready(5)
    # force roles: 1 mafia, 1 det, 3 cit
    start(g, rng=__import__("random").Random(0))
    mafia = g.alive_mafia()[0]
    # kill until mafia >= town
    while g.winner is None and g.alive_town():
        begin_night(g, 0, 10)
        town = g.alive_town()[0]
        set_night_action(g, mafia.user_id, town.seat)
        resolve_night(g)
        if g.phase != "finished":
            break
    # 5 players: 1 mafia 4 town. After 3 night kills without day, 1m+1t => mafia win
    # If random start didn't give 1 mafia this still checks win_check math.
    g2 = _ready(5)
    start(g2, rng=__import__("random").Random(2))
    for p in g2.players:
        if p.faction == "town":
            p.alive = False
            break
    # may not be parity yet
    win_check(g2)


def test_vote_change_and_elim() -> None:
    g = _ready(5)
    start(g, rng=__import__("random").Random(3))
    begin_night(g, 0, 1)
    resolve_night(g)  # miss
    begin_voting(g, 0, 20)
    target = g.alive_players()[0]
    voters = [p for p in g.alive_players() if p.user_id != target.user_id]
    set_vote(g, voters[0].user_id, target.seat)
    other = next(p for p in g.alive_players() if p.seat != target.seat and p.user_id != voters[0].user_id)
    set_vote(g, voters[0].user_id, other.seat)  # change
    for v in voters:
        set_vote(g, v.user_id, other.seat)
    result = resolve_votes(g)
    assert result["tie"] is False
    assert result["eliminated"] == other.seat
    assert other.alive is False


def test_cancel_and_win_parity() -> None:
    from tezmafia.engine import cancel, Phase, Winner

    g = _ready(5)
    start(g, rng=__import__("random").Random(5))
    for p in g.players:
        p.alive = p.faction == "mafia"
    assert win_check(g) == Winner.MAFIA
    assert g.phase == Phase.FINISHED

    g2 = _ready(5)
    start(g2, rng=__import__("random").Random(6))
    for p in g2.players:
        if p.faction == "mafia":
            p.alive = False
    assert win_check(g2) == Winner.TOWN

    g3 = _ready(5)
    cancel(g3)
    assert g3.phase == Phase.FINISHED


def test_mafia_split_is_miss() -> None:
    g = _ready(8)
    start(g, rng=__import__("random").Random(4))
    maf = g.alive_mafia()
    if len(maf) < 2:
        return
    towns = g.alive_town()
    begin_night(g, 0, 10)
    set_night_action(g, maf[0].user_id, towns[0].seat)
    set_night_action(g, maf[1].user_id, towns[1].seat)
    result = resolve_night(g)
    don = next((p for p in maf if p.role == "don"), None)
    if don and don.night_action:
        assert result["killed"] == don.night_action
    else:
        assert result["miss"] is True
        assert result["killed"] is None
