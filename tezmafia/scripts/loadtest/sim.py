"""Random full games through the real engine, with invariants checked after every step.

The same simulator feeds the database generator, so every stored test game is a game the engine
really produced. `play()` never raises on a rule violation; it returns the violations it saw.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass, field

from tezmafia.engine import (
    Game,
    Phase,
    add_bot,
    begin_lynch,
    begin_night,
    begin_voting,
    bot_lynch_votes,
    bot_night_moves,
    bot_votes,
    can_start,
    cancel,
    end_if_stalemate,
    extend_lobby,
    from_dict,
    humans,
    is_bot,
    join,
    kick,
    leave,
    mark_dm_ok,
    new_game,
    peek_votes,
    player_won,
    resolve_lynch,
    resolve_night,
    resolve_votes,
    set_lynch_vote,
    set_night_action,
    set_vote,
    start,
    to_dict,
)
from tezmafia.roles import NIGHT_ROLES, ROLE_FACTION, SPECIALS, Role

MAX_NIGHTS = 60
WINNERS = {"town", "mafia", "maniac", "suicide", "arsonist", "snitch", "mage", "crook", "draw"}
SHOP_FLAGS = ("shop_shield", "shop_vote_shield", "shop_mask", "shop_fake_id", "shop_gun", "shop_killer_shield")


@dataclass
class Result:
    game: Game
    nights: int = 0
    violations: list[str] = field(default_factory=list)
    stalled: bool = False
    # Engine behaviours that are legal today but worth a human decision (see docs/RULES-VERIFICATION.md).
    notes: Counter = field(default_factory=Counter)
    bots: int = 0
    kicks: int = 0


def _check(game: Game, res: Result, where: str) -> None:
    dead = {p.seat for p in game.players if not p.alive}
    logged = Counter(ev["seat"] for ev in game.chronicle)
    if set(logged) != dead:
        missing, extra = sorted(dead - set(logged)), sorted(set(logged) - dead)
        res.violations.append(f"{where}: chronicle/deaths mismatch missing={missing} extra={extra}")
    if any(n > 1 for n in logged.values()):
        res.violations.append(f"{where}: a death logged twice {dict(logged)}")
    if (game.phase == Phase.FINISHED) != bool(game.winner):
        res.violations.append(f"{where}: phase={game.phase} winner={game.winner}")


def _check_end(game: Game, res: Result) -> None:
    if game.winner not in WINNERS:
        res.violations.append(f"end: unknown winner {game.winner}")
        return
    if game.winner == "draw":
        if any(player_won(game, p) for p in game.players):
            res.violations.append("end: draw with winners")
        if game.alive_players() and (game.quiet_rounds < 3 or len(game.alive_players()) > 4):
            res.violations.append("end: stalemate draw outside the rule (3 quiet rounds, at most 4 alive)")
    elif not any(player_won(game, p) for p in game.players):
        res.violations.append(f"end: winner {game.winner} but nobody won")
    alive = game.alive_players()
    mafia = [p for p in alive if p.faction == "mafia"]
    if game.winner == "town" and mafia:
        res.violations.append("end: town won with mafia alive")
    if game.winner == "mafia" and len(mafia) < len(alive) - len(mafia):
        res.violations.append(f"end: mafia won outnumbered {len(mafia)} vs {len(alive) - len(mafia)}")
    raw = to_dict(game)
    if to_dict(from_dict(json.loads(json.dumps(raw)))) != raw:
        res.violations.append("end: serialization round trip changed the game")


def _dead_cannot_act(game: Game, res: Result, rng: random.Random) -> None:
    dead = [p for p in game.players if not p.alive]
    alive = game.alive_players()
    if not dead or not alive:
        return
    p, target = rng.choice(dead), rng.choice(alive)
    if game.phase == Phase.NIGHT and set_night_action(game, p.user_id, target.seat)[0]:
        res.violations.append("night: a dead player acted")
    if game.phase == Phase.VOTING and set_vote(game, p.user_id, target.seat)[0]:
        res.violations.append("vote: a dead player voted")


def play(
    seed: int,
    n: int | None = None,
    user_ids: list[int] | None = None,
    chat_id: int = -1,
    names: list[str] | None = None,
    smart: bool = False,
    extras: bool = False,
) -> Result:
    """smart=True plays like people: killers never aim at their own side, almost everyone acts and votes.

    extras=True adds bots, kicks, role tickets, loadout, lobby churn, mid-game save/restore and the
    non-default table settings (see `play_extras`); the default keeps the original random stream.
    """
    if extras:
        return play_extras(seed, n, user_ids, chat_id, names)
    rng = random.Random(seed)
    n = n or (len(user_ids) if user_ids else rng.randint(5, 23))
    ids = user_ids or list(range(1000, 1000 + n))
    mode = rng.choice(["classic", "classic", "chaos", "secret", "fast"])
    specials = sorted(str(r) for r in SPECIALS)
    disabled = rng.sample(specials, rng.randint(0, min(6, len(specials)))) if rng.random() < 0.3 else []
    game = new_game(chat_id, ids[0], mode=mode, disabled_roles=disabled, anon_vote=rng.random() < 0.3)
    game.created_at = 0.0
    for i, uid in enumerate(ids):
        join(game, uid, names[i] if names else f"P{uid}", None)
        mark_dm_ok(game, uid)
    res = Result(game)
    start(game, rng)
    dealt = {p.role for p in game.players}
    if set(disabled) & dealt:
        res.violations.append(f"start: disabled roles dealt {sorted(set(disabled) & dealt)}")
    for p in game.players:
        for flag in SHOP_FLAGS:
            if rng.random() < 0.04:
                setattr(p, flag, True)

    seats = [p.seat for p in game.players]

    def target(actor=None) -> int:
        # mostly living targets (what real players pick), sometimes any seat to probe the refusals
        alive = [p for p in game.alive_players() if actor is None or p.user_id != actor.user_id]
        if smart and actor is not None and actor.role in ("mafia", "don", "killer"):
            alive = [p for p in alive if p.faction != "mafia"] or alive
        if smart and alive:
            return rng.choice(alive).seat
        return rng.choice([p.seat for p in alive]) if alive and rng.random() < 0.9 else rng.choice(seats)
    while game.phase != Phase.FINISHED:
        if res.nights >= MAX_NIGHTS:
            res.stalled = True
            break
        if end_if_stalemate(game):
            break
        begin_night(game, 0, 1)
        res.nights += 1
        for p in game.alive_players():
            if rng.random() < (0.97 if smart else 0.85):
                set_night_action(game, p.user_id, target(p), "shoot" if rng.random() < 0.3 else "")
        _dead_cannot_act(game, res, rng)
        out = resolve_night(game)
        _check(game, res, f"night {res.nights}")
        if out["winner"] or game.phase == Phase.FINISHED:
            break

        begin_voting(game, 0, 1)
        for p in game.alive_players():
            if rng.random() < (0.95 if smart else 0.8):
                set_vote(game, p.user_id, target(p))
        _dead_cannot_act(game, res, rng)
        seat, tie, _ = peek_votes(game)
        if seat and not tie:
            begin_lynch(game, seat, 0, 1)
            for p in game.alive_players():
                if rng.random() < 0.9:
                    set_lynch_vote(game, p.user_id, rng.random() < 0.6)
            out = resolve_lynch(game)
        else:
            out = resolve_votes(game)
        _check(game, res, f"day {res.nights}")
        if out["winner"]:
            break
    if not res.stalled:
        _check_end(game, res)
    return res


# ---------------------------------------------------------------------------------------------
# Extended simulator: everything added after the first version of this file.
# ---------------------------------------------------------------------------------------------

_NIGHT_VALUES = {r.value for r in NIGHT_ROLES}


def _check_bot_moves(game: Game, res: Result, stage: str) -> None:
    """What the engine promises about bot choices (bot_night_moves / bot_votes / bot_lynch_votes)."""
    alive = game.alive_players()
    for p in alive:
        if not is_bot(p.user_id):
            continue
        others_non_mafia = [q for q in alive if q.user_id != p.user_id and q.faction != "mafia"]
        if stage == "night":
            if p.night_action is None:
                continue
            tgt = game.by_seat(p.night_action)
            if p.role not in _NIGHT_VALUES:
                res.violations.append(f"bot: a bot without a night role acted ({p.role})")
            if not tgt or not tgt.alive or tgt.user_id == p.user_id:
                res.violations.append("bot: night target is dead or the bot itself")
            elif p.faction == "mafia" and tgt.faction == "mafia" and others_non_mafia:
                res.violations.append("bot: a mafia bot aimed at its own faction")
            if p.detective_mode == "shoot" and game.night_no <= 1:
                res.violations.append("bot: detective bot shot on the first night")
        elif stage == "vote" and p.vote:
            tgt = game.by_seat(p.vote)
            if not tgt or not tgt.alive or tgt.user_id == p.user_id:
                res.violations.append("bot: vote for a dead player or itself")
            elif p.faction == "mafia" and tgt.faction == "mafia" and others_non_mafia:
                res.violations.append("bot: a mafia bot voted against its own faction")
        elif stage == "lynch":
            tgt = game.by_seat(game.lynch_seat or -1)
            if tgt and p.user_id == tgt.user_id and p.lynch_yes is not None:
                res.violations.append("bot: the lynch target voted on its own trial")
            if tgt and p.faction == "mafia" and tgt.faction == "mafia" and p.lynch_yes:
                res.violations.append("bot: a mafia bot hanged its own faction")


def _check_seats(game: Game, res: Result, where: str) -> None:
    seats = sorted(p.seat for p in game.players)
    if seats != list(range(1, len(game.players) + 1)):
        res.violations.append(f"{where}: seats are not 1..n {seats}")
    if len({p.user_id for p in game.players}) != len(game.players):
        res.violations.append(f"{where}: duplicate user ids")
    if any(is_bot(p.user_id) for p in humans(game)):
        res.violations.append(f"{where}: humans() returned a bot")


def _dead_cannot_lynch(game: Game, res: Result, rng: random.Random) -> None:
    dead = [p for p in game.players if not p.alive]
    if dead and game.phase == Phase.LYNCH and set_lynch_vote(game, rng.choice(dead).user_id, True)[0]:
        res.violations.append("lynch: a dead player voted")
    tgt = game.by_seat(game.lynch_seat or -1)
    if tgt and game.phase == Phase.LYNCH and tgt.alive and set_lynch_vote(game, tgt.user_id, False)[0]:
        res.violations.append("lynch: the accused voted on their own trial")


def _blocked_cannot_vote(game: Game, res: Result, rng: random.Random) -> None:
    blocked = [p for p in game.alive_players() if p.blocked]
    if blocked and game.phase == Phase.VOTING:
        b = rng.choice(blocked)
        t = rng.choice([p for p in game.alive_players() if p.user_id != b.user_id] or [b])
        if t.user_id != b.user_id and set_vote(game, b.user_id, t.seat)[0]:
            res.violations.append("vote: a player blocked by the hooker voted")


def _refused_after_end(game: Game, res: Result, rng: random.Random) -> None:
    """Once the game is over (or cancelled) nothing may change it."""
    before = to_dict(game)
    alive = game.alive_players()
    for p in alive[:2]:
        t = rng.choice(alive)
        if set_night_action(game, p.user_id, t.seat)[0] or set_vote(game, p.user_id, t.seat)[0]:
            res.violations.append("end: an action was accepted after the game ended")
        if set_lynch_vote(game, p.user_id, True)[0]:
            res.violations.append("end: a lynch vote was accepted after the game ended")
        if kick(game, p.user_id)[0]:
            res.violations.append("end: kick worked after the game ended")
        if leave(game, p.user_id):
            res.violations.append("end: leave worked after the game started")
    for fn in (resolve_night, resolve_votes, resolve_lynch):
        try:
            fn(game)
        except RuntimeError:
            continue
        res.violations.append(f"end: {fn.__name__} ran after the game ended")
    if to_dict(game) != before:
        res.violations.append("end: refused calls still changed the game")


def play_extras(
    seed: int,
    n: int | None = None,
    user_ids: list[int] | None = None,
    chat_id: int = -1,
    names: list[str] | None = None,
) -> Result:
    rng = random.Random(seed)
    xr = random.Random(seed * 2654435761 % (2**32) + 17)  # separate stream for the extra features
    n = n or (len(user_ids) if user_ids else rng.randint(5, 23))
    ids = user_ids or list(range(1000, 1000 + n))
    nb = xr.choice([0, 0, 0, 1, 2, 3, n // 2, n - 1]) if xr.random() < 0.6 else 0
    nb = max(0, min(nb, n - 1))
    mode = rng.choice(["classic", "classic", "chaos", "secret", "fast"])
    specials = sorted(str(r) for r in SPECIALS)
    disabled = rng.sample(specials, rng.randint(0, min(6, len(specials)))) if rng.random() < 0.3 else []
    game = new_game(
        chat_id, ids[0], mode=mode, disabled_roles=disabled, anon_vote=rng.random() < 0.3,
        mafia_resolve=xr.choice(["majority", "majority", "unanimous", "first"]),
        reveal_on_death=xr.random() < 0.7,
        first_phase=xr.choice(["night_kill", "night_kill", "day"]),
    )
    game.created_at = 0.0
    res = Result(game, bots=nb)
    for i, uid in enumerate(ids[: n - nb]):
        join(game, uid, names[i] if names else f"P{uid}", None)
        mark_dm_ok(game, uid)
    for _ in range(nb):
        ok, why = add_bot(game)
        if not ok:
            res.violations.append(f"lobby: add_bot refused ({why})")
    late = 5000 + seed % 1000
    if len(game.players) < 20 and xr.random() < 0.3:  # lobby churn: a late joiner who never opened the bot
        join(game, late, "late", None)
        if can_start(game) != (False, "dm_pending"):
            res.violations.append("lobby: can_start allowed a player who never opened the bot")
        try:
            start(game, rng)
            res.violations.append("lobby: start() accepted a table with a pending DM")
        except RuntimeError:
            pass
        if not leave(game, late):
            res.violations.append("lobby: leave failed")
    if xr.random() < 0.2 and not extend_lobby(game, 30)[0]:
        res.violations.append("lobby: first extend refused")
    _check_seats(game, res, "lobby")
    start(game, rng)
    res.game = game
    dealt = {p.role for p in game.players}
    if set(disabled) & dealt:
        res.violations.append(f"start: disabled roles dealt {sorted(set(disabled) & dealt)}")
    if any(p.role is None or p.faction != ROLE_FACTION[Role(p.role)].value for p in game.players):
        res.violations.append("start: faction does not match role")
    roles_before = Counter(p.role for p in game.players)

    # Role ticket (mirrors App.apply_role_tickets: the holder swaps with whoever has the wanted role).
    if xr.random() < 0.3 and humans(game):
        holder = xr.choice(humans(game))
        want = xr.choice([r.value for r in Role])
        other = next((x for x in game.players if x.role == want and x.user_id != holder.user_id), None)
        if holder.role != want and other:
            holder.role, other.role = other.role, holder.role
            holder.faction = ROLE_FACTION[Role(holder.role)].value
            other.faction = ROLE_FACTION[Role(other.role)].value
            res.notes["ticket_swaps"] += 1
    if Counter(p.role for p in game.players) != roles_before:
        res.violations.append("ticket: the role multiset changed")
    # Loadout (mirrors App.apply_loadout: no pistol for night roles, bots own nothing).
    for p in humans(game):
        for flag in SHOP_FLAGS:
            if xr.random() < 0.05 and not (flag == "shop_gun" and Role(p.role) in NIGHT_ROLES):
                setattr(p, flag, True)
    _check_seats(game, res, "start")

    kicked: list[int] = []
    kick_rate = xr.choice([0, 0, 0.02, 0.05])
    seats = [p.seat for p in game.players]

    def target(actor=None) -> int:
        alive = [p for p in game.alive_players() if actor is None or p.user_id != actor.user_id]
        return rng.choice([p.seat for p in alive]) if alive and rng.random() < 0.9 else rng.choice(seats)

    def maybe_kick(stage: str) -> bool:
        """Admin removes a random living player; True when that ended the game."""
        if xr.random() >= kick_rate or not game.alive_players():
            return False
        victim = xr.choice(game.alive_players())
        if stage == "lynch" and xr.random() < 0.5 and game.lynch_seat:
            victim = game.by_seat(game.lynch_seat) or victim
            if not victim.alive:
                return False
        before = len(game.chronicle)
        done, winner = kick(game, victim.user_id)
        if not done:
            res.violations.append(f"kick({stage}): refused for a living player")
            return False
        res.kicks += 1
        kicked.append(victim.user_id)
        if victim.alive or victim.night_action is not None or victim.vote is not None:
            res.violations.append("kick: the player is still alive or still holds an action")
        if len(game.chronicle) != before + 1 or game.chronicle[-1]["cause"] != "kick":
            res.violations.append("kick: not logged exactly once as kick")
        if any(q.vote == victim.seat for q in game.players):
            res.violations.append("kick: votes against the kicked player were not cleared")
        if bool(winner) != (game.phase == Phase.FINISHED) or winner != game.winner:
            res.violations.append(f"kick: winner/phase mismatch winner={winner} phase={game.phase}")
        return game.phase == Phase.FINISHED

    def roundtrip() -> None:
        nonlocal game
        if xr.random() < 0.15:
            raw = to_dict(game)
            back = from_dict(json.loads(json.dumps(raw)))
            if to_dict(back) != raw:
                res.violations.append("save/restore: the game changed in the round trip")
            game = back
            res.game = game

    def night() -> bool:
        begin_night(game, 0, 1)
        res.nights += 1
        bot_night_moves(game, xr)
        _check_bot_moves(game, res, "night")
        if maybe_kick("night-pre"):
            return True
        for p in game.alive_players():
            if not is_bot(p.user_id) and rng.random() < 0.85:
                set_night_action(game, p.user_id, target(p), "shoot" if rng.random() < 0.3 else "")
        _dead_cannot_act(game, res, rng)
        roundtrip()
        if maybe_kick("night-post"):  # after actions were submitted
            return True
        duty = {
            p.user_id: bool(p.role and Role(p.role) in NIGHT_ROLES) or p.shop_gun for p in game.alive_players()
        }
        sent = {p.user_id for p in game.alive_players() if p.night_action}
        idle = {p.user_id: p.idle_nights for p in game.alive_players()}
        out = resolve_night(game)
        _check(game, res, f"night {res.nights}")
        for seat in out["afk"]:
            p = game.by_seat(seat)
            if not p or p.alive or not duty.get(p.user_id) or p.user_id in sent or idle.get(p.user_id, 0) < 1:
                res.violations.append("afk: removed a player who was not idle for 2 nights")
        for p in game.alive_players():
            still_on_duty = bool(p.role and Role(p.role) in NIGHT_ROLES) or p.shop_gun
            if p.user_id in sent and p.idle_nights and still_on_duty:
                res.violations.append("afk: a player who acted kept an idle count")
            if not duty.get(p.user_id) and p.idle_nights != idle.get(p.user_id, 0):
                res.violations.append("afk: a player without night duty was counted idle")
            if p.shop_gun and not (p.role and Role(p.role) in NIGHT_ROLES) and p.user_id not in sent:
                res.notes["unused_pistol_counts_as_afk"] += 1
        if len(set(out["deaths"])) != len(out["deaths"]):
            res.violations.append("night: the same death reported twice")
        return bool(out["winner"]) or game.phase == Phase.FINISHED

    def day() -> bool:
        begin_voting(game, 0, 1)
        bot_votes(game, xr)
        _check_bot_moves(game, res, "vote")
        for p in game.alive_players():
            if not is_bot(p.user_id) and rng.random() < 0.8:
                set_vote(game, p.user_id, target(p))
        _dead_cannot_act(game, res, rng)
        _blocked_cannot_vote(game, res, rng)
        roundtrip()
        if maybe_kick("vote"):
            return True
        seat, tie, _ = peek_votes(game)
        if seat and not tie:
            accused = game.by_seat(seat)
            begin_lynch(game, seat, 0, 1)
            bot_lynch_votes(game, xr)
            _check_bot_moves(game, res, "lynch")
            for p in game.alive_players():
                if not is_bot(p.user_id) and rng.random() < 0.9:
                    set_lynch_vote(game, p.user_id, rng.random() < 0.6)
            _dead_cannot_lynch(game, res, rng)
            roundtrip()
            if maybe_kick("lynch"):
                return True
            accused_alive = bool(accused and accused.alive)
            out = resolve_lynch(game)
            if out["eliminated"] and not accused_alive:
                res.violations.append("lynch: reported a player kicked during the trial as hanged")
            if out["eliminated"] and not out["confirmed"]:
                res.violations.append("lynch: eliminated although the trial was not confirmed")
        else:
            out = resolve_votes(game)
            if tie and out["eliminated"]:
                res.violations.append("vote: eliminated on a tie")
        _check(game, res, f"day {res.nights}")
        return bool(out["winner"])

    finished = False
    if game.first_phase != "night_kill":
        game.phase = Phase.DAY  # App.enter_day(from_night=False)
        game.round = 1
        finished = day()
    while not finished and game.phase != Phase.FINISHED:
        if res.nights >= MAX_NIGHTS:
            res.stalled = True
            break
        if end_if_stalemate(game):
            break
        if night():
            break
        if xr.random() < 0.004:  # the host runs /stop
            cancel(game)
            _refused_after_end(game, res, rng)
            return res
        if day():
            break
    if not res.stalled:
        if game.phase != Phase.FINISHED:
            res.violations.append("end: loop left an unfinished game")
        else:
            _check(game, res, "end")
            _check_end(game, res)
            _refused_after_end(game, res, rng)
            for uid in kicked:
                p = game.by_user(uid)
                if p and p.alive:
                    res.violations.append("kick: a kicked player is alive at the end")
                if p and player_won(game, p):
                    res.notes["kicked_player_counted_as_winner"] += 1
    _check_seats(game, res, "end")
    return res
