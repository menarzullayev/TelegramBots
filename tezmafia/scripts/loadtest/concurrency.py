"""Many groups playing full games at the same time through the real App and handlers.

    python -m scripts.loadtest.concurrency --db PATH --steps 10,100,1000 [--latency 0.08]

Telegram is replaced by the unit tests' FakeBot with an artificial network latency (default 80 ms),
because the bot really waits on Telegram while it holds a chat lock. Timers are pushed far out and
each phase is driven explicitly with the same App methods the timers call. Players are synthetic
users from the generated pool, so game-end statistics are written to existing rows.

Checks per step: every game ends, no exception, no lost update (each player's stats.games grows by
exactly the number of games they finished), and the latency of every operation.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import random
import statistics
import time
from collections import defaultdict
from types import SimpleNamespace

from aiogram.enums import ChatType
from aiogram.types import Chat, User

from scripts.loadtest.generate import FAKE_CHAT, FAKE_USER

MAX_NIGHTS = 40


class Meter:
    def __init__(self) -> None:
        self.ops: dict[str, list[float]] = defaultdict(list)
        self.errors: list[str] = []
        self.api_calls = 0

    async def time(self, name: str, coro):
        t0 = time.perf_counter()
        try:
            return await coro
        except Exception as e:  # noqa: BLE001 - every failure is a finding
            self.errors.append(f"{name}: {type(e).__name__}: {e}"[:300])
            return None
        finally:
            self.ops[name].append((time.perf_counter() - t0) * 1000)


def slow_bot(latency: float, meter: Meter):
    from tests.test_bot_e2e import FakeBot

    bot = FakeBot()
    for name, fn in inspect.getmembers(bot, inspect.iscoroutinefunction):
        if name.startswith("_"):
            continue

        def wrap(f):
            async def inner(*a, **k):
                meter.api_calls += 1
                await asyncio.sleep(latency * random.uniform(0.5, 1.5))
                return await f(*a, **k)

            return inner

        setattr(bot, name, wrap(fn))
    return bot


def msg(bot, uid: int, chat_id: int, text: str, private: bool = False):
    from tests.test_bot_e2e import FakeMsg

    chat = Chat(id=uid if private else chat_id, type=ChatType.PRIVATE if private else ChatType.SUPERGROUP)
    m = FakeMsg(User(id=uid, is_bot=False, first_name=f"L{uid % 10000}"), chat, text, bot)
    m.reply_to_message = None  # type: ignore[attr-defined]
    return m


async def play_one(app, botmod, meter: Meter, chat_id: int, players: list[int], rng: random.Random) -> str:
    from tezmafia.engine import Phase, set_lynch_vote, set_night_action, set_vote

    host = players[0]
    await meter.time("cmd_mafia(open lobby)", botmod.cmd_mafia(msg(app.bot, host, chat_id, "/game")))
    await asyncio.gather(*(meter.time("cmd_join", botmod.cmd_join(msg(app.bot, u, chat_id, "/join"))) for u in players[1:]))
    game = await app.store.active_in_chat(chat_id)
    if not game:
        return "no_lobby"
    await asyncio.gather(*(
        meter.time("cmd_start(dm deep link)", botmod.cmd_start(msg(app.bot, u, chat_id, f"/start g_{game.id}", True),
                                                            SimpleNamespace(args=f"g_{game.id}")))
        for u in players
    ))
    async with app.game_lock(game.id):
        game = await app.store.load(game.id)
        await meter.time("start_game", app.start_game(game))
    gid = game.id
    for _ in range(MAX_NIGHTS):
        game = await app.store.load(gid)
        if game.phase == Phase.FINISHED:
            return "finished"
        if game.phase == Phase.NIGHT:
            async def act(p):
                async with app.game_lock(gid):
                    g = await app.store.load(gid)
                    alive = [x.seat for x in g.alive_players()]
                    set_night_action(g, p.user_id, rng.choice(alive), "shoot" if rng.random() < 0.3 else "")
                    await app.persist(g)
            await asyncio.gather(*(meter.time("night_action", act(p)) for p in game.alive_players() if rng.random() < 0.9))
            await meter.time("resolve_night", app._timed_resolve_night(gid))
        elif game.phase == Phase.DAY:
            await meter.time("begin_vote", app._timed_begin_vote(gid))
        elif game.phase == Phase.VOTING:
            async def vote(p):
                async with app.game_lock(gid):
                    g = await app.store.load(gid)
                    others = [x.seat for x in g.alive_players() if x.user_id != p.user_id]
                    if others:
                        set_vote(g, p.user_id, rng.choice(others[:3]))
                        await app.persist(g)
            await asyncio.gather(*(meter.time("vote", vote(p)) for p in game.alive_players() if rng.random() < 0.9))
            await meter.time("resolve_vote", app._timed_resolve_vote(gid))
        elif game.phase == Phase.LYNCH:
            async def lynch(p):
                async with app.game_lock(gid):
                    g = await app.store.load(gid)
                    set_lynch_vote(g, p.user_id, rng.random() < 0.7)
                    await app.persist(g)
            await asyncio.gather(*(meter.time("lynch_vote", lynch(p)) for p in game.alive_players()))
            await meter.time("resolve_lynch", app._timed_resolve_lynch(gid))
        else:
            return f"phase:{game.phase}"
    return "stuck"


async def run_step(app, botmod, n_chats: int, rng: random.Random, latency: float) -> dict:
    from sqlalchemy import text

    meter = Meter()
    app.bot = slow_bot(latency, meter)
    base_chat = FAKE_CHAT - 50_000 - rng.randrange(10_000_000)
    pool = rng.sample(range(100_000, 900_000), n_chats * 12)
    tables = []
    for i in range(n_chats):
        size = rng.randint(6, 12)
        tables.append((base_chat - i, [FAKE_USER + u for u in pool[i * 12 : i * 12 + size]]))
    everyone = [u for _, ps in tables for u in ps]
    async with app.store.engine.connect() as conn:
        rows = await conn.execute(text(f"SELECT user_id, games FROM stats WHERE user_id IN ({','.join(map(str, everyone))})"))
        before = {r[0]: r[1] for r in rows}
    t0 = time.perf_counter()
    outcomes = await asyncio.gather(*(play_one(app, botmod, meter, c, ps, random.Random(rng.random())) for c, ps in tables))
    wall = time.perf_counter() - t0
    for task in list(app.timers.values()):
        task.cancel()
    app.timers.clear()
    await asyncio.sleep(0.5)  # let cancelled timers unwind
    async with app.store.engine.connect() as conn:
        rows = await conn.execute(text(f"SELECT user_id, games FROM stats WHERE user_id IN ({','.join(map(str, everyone))})"))
        after = {r[0]: r[1] for r in rows}
    finished_players = {u for (c, ps), o in zip(tables, outcomes, strict=True) if o == "finished" for u in ps}
    lost = [u for u in finished_players if after.get(u, 0) - before.get(u, 0) != 1]
    ops = {
        k: {"n": len(v), "p50": round(statistics.median(v), 1), "p95": round(sorted(v)[int(len(v) * 0.95) - 1 if len(v) > 1 else 0], 1),
            "max": round(max(v), 1)}
        for k, v in meter.ops.items()
    }
    out = {
        "chats": n_chats, "players": len(everyone), "wall_s": round(wall, 1),
        "outcomes": {o: outcomes.count(o) for o in set(outcomes)},
        "lost_or_double_stat_updates": len(lost), "errors": len(meter.errors), "error_samples": meter.errors[:8],
        "telegram_calls": meter.api_calls, "telegram_calls_per_s": round(meter.api_calls / wall, 1), "ops": ops,
    }
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--steps", default="10,100,1000")
    ap.add_argument("--latency", type=float, default=0.08)
    ap.add_argument("--json")
    args = ap.parse_args()

    from tezmafia import bot as botmod
    from tezmafia.bot import App
    from tezmafia.config import Settings
    from tezmafia.db import Store

    settings = Settings(bot_token="1:LOAD", bot_username="qorashahar_mafia_bot", owner_id=1,
                        night_action_seconds=100_000, voting_seconds=100_000, lynch_seconds=100_000,
                        lobby_seconds=100_000, discussion_seconds=100_000)
    store = Store(f"sqlite+aiosqlite:///{args.db}")
    app = App(settings, store, None)  # type: ignore[arg-type]
    botmod.app = app
    rng = random.Random(42)
    report = []
    for n in [int(x) for x in args.steps.split(",")]:
        print(f"--- {n} chats at once ---", flush=True)
        r = await run_step(app, botmod, n, rng, args.latency)
        report.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "ops"}, ensure_ascii=False), flush=True)
        for k, v in sorted(r["ops"].items(), key=lambda kv: -kv[1]["p95"]):
            print(f"   {k:26} n={v['n']:>6}  p50 {v['p50']:>8} ms  p95 {v['p95']:>8}  max {v['max']:>8}", flush=True)
    await store.engine.dispose()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())
