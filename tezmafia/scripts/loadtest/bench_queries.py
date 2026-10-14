"""Time every hot Store call (and the Mini App state) against a big database.

    python -m scripts.loadtest.bench_queries --db PATH [--runs 30] [--json out.json]

Reads use random synthetic users/chats each run, so the cache cannot hide a missing index.
Writes go to synthetic rows only. Prints p50 / p95 / max in milliseconds per call.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from types import SimpleNamespace

from scripts.loadtest.generate import FAKE_CHAT, FAKE_USER

OWNER = 1808327630


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--json")
    ap.add_argument("--with-delete", action="store_true", help="also time delete_user (scans every finished game)")
    args = ap.parse_args()

    from tezmafia.db import Store
    from tezmafia.engine import join, mark_dm_ok, new_game, start
    from tezmafia.social import week_key
    from tezmafia.webapp.server import build_state

    store = Store(f"sqlite+aiosqlite:///{args.db}")
    rng = random.Random(7)
    season, week = time.strftime("%Y-%m"), week_key()
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    month = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))
    n_users = await _count(store, "stats")
    real_chat = -5042113726

    def u() -> int:
        return FAKE_USER + int(rng.random() ** 2 * (n_users - 10))

    def c() -> int:
        return FAKE_CHAT - rng.randrange(20_000)

    def a_game():
        g = new_game(c(), u())
        for i in range(10):
            join(g, FAKE_USER + 500_000 + rng.randrange(400_000) + i, "Bench", None)
        for p in g.players:
            mark_dm_ok(g, p.user_id)
        start(g, rng)
        return g

    saved: list = []
    any_game = await _one(store, "SELECT id FROM games WHERE chat_id <= ? LIMIT 1", (FAKE_CHAT,))
    clan_id = await _one(store, "SELECT id FROM clans ORDER BY id DESC LIMIT 1")
    fake_app = SimpleNamespace(store=store)

    ops = {
        # per message / per callback
        "active_in_chat": lambda: store.active_in_chat(c()),
        "get_lang": lambda: store.get_lang(c()),
        "chat_settings": lambda: store.chat_settings(c()),
        "is_banned": lambda: store.is_banned(c(), u()),
        "touch_activity": lambda: store.touch_activity(time.strftime("%Y-%m-%d"), u(), "group"),
        "load(game)": lambda: store.load(any_game),
        "save(game)": lambda: _save(store, a_game(), saved),
        # commands
        "get_account": lambda: store.get_account(u()),
        "achievement_count": lambda: store.achievement_count(u()),
        "fair_play": lambda: store.fair_play(u()),
        "season_top(global)": lambda: store.season_top(season),
        "season_top(chat)": lambda: store.season_top(season, chat_id=c()),
        "top_stats(all time)": lambda: store.top_stats(),
        "recent_games(chat)": lambda: store.recent_games(c()),
        "user_games(owner)": lambda: store.user_games(OWNER),
        "user_games(random)": lambda: store.user_games(u()),
        "group_stats(real)": lambda: store.group_stats(real_chat, season),
        "group_stats(random)": lambda: store.group_stats(c(), season),
        "week_top": lambda: store.week_top(week),
        "clan_top": lambda: store.clan_top(season),
        "clan_stats": lambda: store.clan_stats(clan_id, season),
        "clan_of": lambda: store.clan_of(u()),
        "referral_count": lambda: store.referral_count(u()),
        "by_user_lobby_or_live": lambda: store.by_user_lobby_or_live(u()),
        "games_for_user": lambda: store.games_for_user(u()),
        # game end (record_stats writes these per player)
        "bump_stat": lambda: store.bump_stat(u(), "Bench", rng.random() < 0.5, True),
        "bump_season": lambda: store.bump_season(season, c(), u(), "Bench", True),
        "bump_week": lambda: store.bump_week(week, u(), "Bench", True, 4),
        "link_game": lambda: store.link_game(f"bench{rng.randrange(1 << 40)}", [u() for _ in range(10)]),
        "adjust_fair_play": lambda: store.adjust_fair_play(u(), False, 15, 3),
        "award": lambda: store.award(u(), {"first_game"}),
        # background loops / reports
        "streaks_at_risk": lambda: store.streaks_at_risk(yesterday),
        "active_users(30d)": lambda: store.active_users(month),
        "report_since(24h)": lambda: store.report_since(time.time() - 86400),
        "unfinished(startup)": lambda: store.unfinished(),
        # Mini App
        "miniapp build_state": lambda: build_state(fake_app, {"id": u(), "first_name": "B", "language_code": "uz"}),
        "miniapp build_state(owner)": lambda: build_state(fake_app, {"id": OWNER, "first_name": "S", "language_code": "uz"}),
    }
    slow = {"top_stats(all time)", "group_stats(real)", "active_users(30d)", "report_since(24h)", "clan_top", "unfinished(startup)"}
    results = {}
    for name, fn in ops.items():
        runs = max(3, args.runs // 6) if name in slow else args.runs
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            await fn()
            times.append((time.perf_counter() - t0) * 1000)
        times.sort()
        results[name] = {
            "p50": round(statistics.median(times), 2),
            "p95": round(times[min(len(times) - 1, int(len(times) * 0.95))], 2),
            "max": round(times[-1], 2),
            "runs": runs,
        }
        r = results[name]
        print(f"{name:28} p50 {r['p50']:>9.2f} ms   p95 {r['p95']:>9.2f}   max {r['max']:>9.2f}   (n={runs})", flush=True)
    if args.with_delete:
        t0 = time.perf_counter()
        await store.delete_user(FAKE_USER + n_users - 20)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        results["delete_user"] = {"p50": ms, "p95": ms, "max": ms, "runs": 1}
        print(f"{'delete_user':28} {ms:>9.1f} ms (1 run)")
    # tidy the benchmark's own writes
    await _exec(store, "DELETE FROM games WHERE id IN ({})".format(",".join("?" * len(saved))), saved) if saved else None
    await _exec(store, "DELETE FROM game_players WHERE game_id LIKE 'bench%'")
    await store.engine.dispose()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)


async def _save(store, game, saved: list) -> None:
    game.phase = "finished"
    await store.save(game)
    saved.append(game.id)


async def _count(store, table: str) -> int:
    return await _one(store, f"SELECT COUNT(*) FROM {table}")


async def _one(store, sql: str, params: tuple = ()):
    from sqlalchemy import text

    async with store.engine.connect() as conn:
        res = await conn.exec_driver_sql(sql, params) if params else await conn.execute(text(sql))
        return res.scalar()


async def _exec(store, sql: str, params=()) -> None:
    async with store.engine.begin() as conn:
        await conn.exec_driver_sql(sql, tuple(params))


if __name__ == "__main__":
    asyncio.run(main())
