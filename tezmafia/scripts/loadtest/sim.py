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
    begin_lynch,
    begin_night,
    begin_voting,
    from_dict,
    join,
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
from tezmafia.roles import SPECIALS

MAX_NIGHTS = 60
WINNERS = {"town", "mafia", "maniac", "suicide", "arsonist", "snitch", "mage", "crook"}
SHOP_FLAGS = ("shop_shield", "shop_vote_shield", "shop_mask", "shop_fake_id", "shop_gun", "shop_killer_shield")


@dataclass
class Result:
    game: Game
    nights: int = 0
    violations: list[str] = field(default_factory=list)
    stalled: bool = False


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
    if not any(player_won(game, p) for p in game.players):
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
) -> Result:
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

    def target() -> int:
        # mostly living targets (what real players pick), sometimes any seat to probe the refusals
        alive = [p.seat for p in game.alive_players()]
        return rng.choice(alive) if alive and rng.random() < 0.9 else rng.choice(seats)
    while game.phase != Phase.FINISHED:
        if res.nights >= MAX_NIGHTS:
            res.stalled = True
            break
        begin_night(game, 0, 1)
        res.nights += 1
        for p in game.alive_players():
            if rng.random() < 0.85:
                set_night_action(game, p.user_id, target(), "shoot" if rng.random() < 0.3 else "")
        _dead_cannot_act(game, res, rng)
        out = resolve_night(game)
        _check(game, res, f"night {res.nights}")
        if out["winner"] or game.phase == Phase.FINISHED:
            break

        begin_voting(game, 0, 1)
        for p in game.alive_players():
            if rng.random() < 0.8:
                set_vote(game, p.user_id, target())
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
