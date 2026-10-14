"""Fill a TezMafia database with synthetic users and engine-played finished games.

    python -m scripts.loadtest.generate --db PATH [--users 1000000] [--games 1000000] [--workers 22]

Synthetic ids live far outside Telegram's ranges (users 9e12+, chats -9e12-), so the bot never
messages them for real and `cleanup.py` removes them with one range query. Writes go in short
transactions so a running bot only waits (busy_timeout) instead of failing. Every phase is timed;
the timings are printed as JSON at the end (the "insert speed" part of the load report).
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import time
from bisect import bisect
from itertools import accumulate
from multiprocessing import Pool

FAKE_USER = 9_000_000_000_000
FAKE_CHAT = -9_000_000_000_000
DAYS = 85  # inside the bot's 90-day retention, so the daily prune keeps them
CHUNK = 10_000

FIRST = (
    "Aziz Bobur Dilnoza Malika Sardor Jasur Nodira Shahzod Kamola Otabek Zarina Ulugbek Madina Sherzod Nilufar "
    "Javohir Gulnora Farrux Sevara Akmal Ivan Olga Dmitry Anna Sergey Elena Alex Maria John Emma Mehmet Ayse Emre "
    "Zeynep Nurlan Aigerim Daniyar Asel Rustam Firuza Timur Leyla Farid Aysel Bekzod Laylo Islom Mohira"
).split()
LAST = ("", "", "", " A.", " B.", " 777", " UZ", " ✨", " 🦅", " Pro", " Boss", " 2009", " TV", " ⚡")
CLAN_WORDS = (
    "Qora Oq Tun Burgut Bo'ri Arslon Shamol Tog' Daryo Yulduz Qarg'a Soya Olov Muz Temir Oltin Kumush Chaqmoq Ko'k "
    "Night Wolf Raven Storm Iron Ghost Shadow Fire Ice Steel Lion Hawk Red Black Silver Moon Sun Star Blood Stone"
).replace("'", "").split()
ACH = ("first_game", "games_10", "games_50", "first_win", "survivor", "win_mafia", "win_town", "level_5")
BADGE_EMOJI = ("", "", "", "⭐", "🌹", "💀", "🔥", "👑")
LANGS = ("uz", "ru", "en", "kz", "tr", "az", "kg", "tj", "ua", "id", "br")


def _name(rng: random.Random) -> str:
    return rng.choice(FIRST) + rng.choice(LAST)


def _play(spec: tuple) -> tuple:
    """Worker: one engine game -> row data. Top level so multiprocessing can pickle it."""
    from scripts.loadtest.sim import play
    from tezmafia.engine import player_won, to_dict
    from tezmafia.progress import xp_for

    seed, chat_id, ids, names, ts = spec
    res = play(seed, user_ids=ids, chat_id=chat_id, names=names)
    g = res.game
    g.created_at = ts
    if res.stalled:  # keep stored games finished, like a host /stop would
        g.phase, g.winner = "finished", None
    parts = [(p.user_id, p.first_name, int(player_won(g, p)), int(p.alive), xp_for(player_won(g, p), p.alive)) for p in g.players]
    return g.id, chat_id, json.dumps(to_dict(g), ensure_ascii=False), g.version, ts, parts, len(res.violations), res.stalled


def _connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA synchronous=OFF")  # this connection only; the bot's own writes stay durable
    con.execute("PRAGMA cache_size=-512000")
    return con


def _batched(con: sqlite3.Connection, sql: str, rows: list, size: int = 20_000) -> None:
    for i in range(0, len(rows), size):
        con.execute("BEGIN IMMEDIATE")
        con.executemany(sql, rows[i : i + size])
        con.execute("COMMIT")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--users", type=int, default=1_000_000)
    ap.add_argument("--games", type=int, default=1_000_000)
    ap.add_argument("--workers", type=int, default=22)
    ap.add_argument("--seed", type=int, default=20261014)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    con = _connect(args.db)
    timings: dict[str, float] = {}
    now = time.time()

    def phase(name: str, t0: float) -> None:
        timings[name] = round(time.perf_counter() - t0, 2)
        print(f"  {name}: {timings[name]} s", flush=True)

    # --- users -----------------------------------------------------------------------------------
    t0 = time.perf_counter()
    names = [_name(rng) for _ in range(args.users)]
    user_rows = []
    for i, name in enumerate(names):
        badge = rng.choice(BADGE_EMOJI)
        user_rows.append((
            FAKE_USER + i, name, 0, 0, rng.randint(0, 3000) if rng.random() < 0.7 else 0, rng.randint(0, 40),
            "{}", "", now - rng.random() * DAYS * 86400,
            now + rng.random() * 30 * 86400 if rng.random() < 0.02 else None,
            badge, json.dumps([k for k, (e, _c) in {"star": ("⭐", 0), "rose": ("🌹", 0), "skull": ("💀", 0),
                              "fire": ("🔥", 0), "crown": ("👑", 0)}.items() if e == badge]), 0, "", 0,
        ))
    _batched(con, "INSERT OR REPLACE INTO stats (user_id, name, games, wins, coins, gems, inventory, next_role, first_seen,"
             " vip_until, badge, badges, xp, daily_last, daily_streak) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", user_rows)
    del user_rows
    phase("users_insert", t0)

    t0 = time.perf_counter()
    fair = [(FAKE_USER + i, 100 if rng.random() < 0.8 else rng.randint(20, 99), rng.randint(0, 6)) for i in range(args.users)]
    _batched(con, "INSERT OR REPLACE INTO fair_play (user_id, score, afk) VALUES (?,?,?)", fair)
    prefs = [(FAKE_USER + i, rng.choice(LANGS)) for i in rng.sample(range(args.users), args.users // 3)]
    _batched(con, "INSERT OR REPLACE INTO prefs (chat_id, lang) VALUES (?,?)", prefs)
    ach = [(FAKE_USER + i, k, now - rng.random() * DAYS * 86400)
           for i in range(args.users) for k in ACH if rng.random() < 0.25]
    _batched(con, "INSERT OR IGNORE INTO achievements (user_id, key, at) VALUES (?,?,?)", ach)
    refs = [(FAKE_USER + i, FAKE_USER + rng.randrange(i), now - rng.random() * DAYS * 86400, 1)
            for i in rng.sample(range(1, args.users), args.users // 10)]
    _batched(con, "INSERT OR IGNORE INTO referrals (user_id, referrer_id, at, rewarded) VALUES (?,?,?,?)", refs)
    timings["side_rows"] = len(fair) + len(prefs) + len(ach) + len(refs)
    del fair, prefs, ach, refs
    phase("side_tables_insert", t0)

    # clans: 5000 clans, 150k members
    t0 = time.perf_counter()
    n_members = min(150_000, args.users * 15 // 100)
    n_clans = max(1, min(5000, n_members // 30))
    clan_names, seen = [], set()
    while len(clan_names) < n_clans:
        n = f"{rng.choice(CLAN_WORDS)} {rng.choice(CLAN_WORDS)}{'' if rng.random() < 0.6 else ' ' + str(rng.randint(1, 99))}"
        if n.casefold() not in seen:
            seen.add(n.casefold())
            clan_names.append(n)
    members = rng.sample(range(args.users), n_members)
    con.execute("BEGIN IMMEDIATE")
    base = (con.execute("SELECT COALESCE(MAX(id), 0) FROM clans").fetchone()[0]) + 1
    con.executemany("INSERT INTO clans (id, name, name_key, owner_id, created_at) VALUES (?,?,?,?,?)",
                    [(base + k, n, n.casefold(), FAKE_USER + members[k], now - rng.random() * DAYS * 86400)
                     for k, n in enumerate(clan_names)])
    con.execute("COMMIT")
    _batched(con, "INSERT OR IGNORE INTO clan_members (user_id, clan_id, joined_at) VALUES (?,?,?)",
             [(FAKE_USER + u, base + (k if k < n_clans else rng.randrange(n_clans)), now - rng.random() * DAYS * 86400)
              for k, u in enumerate(members)])
    phase("clans_insert", t0)

    # --- chats and their regulars ----------------------------------------------------------------
    real_users = con.execute("SELECT user_id, name FROM stats WHERE user_id < ?", (FAKE_USER,)).fetchall()
    real_chats = [r[0] for r in con.execute("SELECT DISTINCT chat_id FROM games WHERE chat_id > ?", (FAKE_CHAT,))]
    chats: list[tuple[int, list[int]]] = []
    for c in range(max(10, min(20_000, args.users // 50))):
        size = min(400, max(6, int(rng.paretovariate(1.3) * 12)))
        pool = list({int(args.users * rng.random() ** 2) for _ in range(size)})
        chats.append((FAKE_CHAT - c, pool))
    weights = list(accumulate(len(p) for _, p in chats))
    real_share = max(1, args.games // 300)  # games per real group, so their /groupstats fills up

    def spec(k: int) -> tuple:
        ts = now - rng.random() * DAYS * 86400
        n = min(23, max(5, int(rng.gauss(10, 4))))
        if k < real_share * len(real_chats):
            chat_id = real_chats[k // real_share]
            reals = [u for u in real_users if rng.random() < 0.6]
            fakes = [int(args.users * rng.random() ** 2) for _ in range(n)]
            ids = [u for u, _ in reals] + [FAKE_USER + f for f in dict.fromkeys(fakes)]
            nm = [x for _, x in reals] + [names[f] for f in dict.fromkeys(fakes)]
        else:
            chat_id, pool = chats[bisect(weights, rng.random() * weights[-1])]
            pick = rng.sample(pool, min(n, len(pool)))
            if len(pick) < 5:
                pick += [int(args.users * rng.random()) for _ in range(5 - len(pick))]
                pick = list(dict.fromkeys(pick))
            ids = [FAKE_USER + f for f in pick]
            nm = [names[f] for f in pick]
        ids, nm = ids[:23], nm[:23]
        return (rng.randrange(1 << 62), chat_id, ids, nm, ts)

    # --- games -----------------------------------------------------------------------------------
    con.execute("DROP TABLE IF EXISTS lt_part")
    con.execute("CREATE TABLE lt_part (user_id INTEGER, name TEXT, chat_id INTEGER, season TEXT, week TEXT, day TEXT,"
                " won INTEGER, alive INTEGER, xp INTEGER)")
    t0 = time.perf_counter()
    sim_s = insert_s = 0.0
    bad = stalled = done = parts_total = 0
    with Pool(args.workers) as pool:
        for start in range(0, args.games, CHUNK):
            specs = [spec(k) for k in range(start, min(args.games, start + CHUNK))]
            t1 = time.perf_counter()
            rows = pool.map(_play, specs, chunksize=50)
            sim_s += time.perf_counter() - t1
            t1 = time.perf_counter()
            games, gp, part = [], [], []
            for gid, chat_id, payload, version, ts, parts, nviol, st in rows:
                games.append((gid, chat_id, "finished", payload, version, ts, ts))
                lt = time.localtime(ts)
                season, week, day = time.strftime("%Y-%m", lt), time.strftime("%G-W%V", lt), time.strftime("%Y-%m-%d", lt)
                for uid, nm, won, alive, xp in parts:
                    gp.append((gid, uid, ts))
                    part.append((uid, nm, chat_id, season, week, day, won, alive, xp))
                bad += nviol > 0
                stalled += st
            con.execute("BEGIN IMMEDIATE")
            con.executemany("INSERT OR IGNORE INTO games (id, chat_id, status, payload, version, created_at, updated_at)"
                            " VALUES (?,?,?,?,?,?,?)", games)
            con.executemany("INSERT OR IGNORE INTO game_players (game_id, user_id, at) VALUES (?,?,?)", gp)
            con.executemany("INSERT INTO lt_part VALUES (?,?,?,?,?,?,?,?,?)", part)
            con.execute("COMMIT")
            insert_s += time.perf_counter() - t1
            done += len(rows)
            parts_total += len(part)
            el = time.perf_counter() - t0
            print(f"  games {done:,}/{args.games:,}  {done / el:,.0f}/s  (sim {sim_s:.0f}s, insert {insert_s:.0f}s)", flush=True)
    timings.update(games_total=round(time.perf_counter() - t0, 1), games_sim=round(sim_s, 1),
                   games_insert=round(insert_s, 1), participations=parts_total, games_with_violations=bad,
                   games_stalled=stalled)

    # --- aggregates (what bump_stat / bump_season / bump_week would have written) -----------------
    t0 = time.perf_counter()
    con.execute("CREATE INDEX lt_part_u ON lt_part(user_id)")
    con.execute("BEGIN IMMEDIATE")
    con.execute("UPDATE stats SET games = COALESCE(games, 0) + a.g, wins = COALESCE(wins, 0) + a.w, xp = COALESCE(xp, 0) + a.x,"
                " coins = COALESCE(coins, 0) + 10 * a.g + 25 * a.w, gems = COALESCE(gems, 0) + a.w"
                " FROM (SELECT user_id, COUNT(*) g, SUM(won) w, SUM(xp) x FROM lt_part GROUP BY user_id) a"
                " WHERE stats.user_id = a.user_id")
    con.execute("COMMIT")
    phase("agg_stats", t0)
    t0 = time.perf_counter()
    con.execute("BEGIN IMMEDIATE")
    for chat_expr, group in (("chat_id", "season, chat_id, user_id"), ("0", "season, user_id")):
        con.execute(f"INSERT INTO season_stats (season, chat_id, user_id, name, games, wins)"
                    f" SELECT season, {chat_expr}, user_id, MAX(name), COUNT(*), SUM(won) FROM lt_part"
                    f" WHERE true GROUP BY {group}"
                    f" ON CONFLICT(season, chat_id, user_id) DO UPDATE SET games = games + excluded.games,"
                    f" wins = wins + excluded.wins")
    con.execute("COMMIT")
    phase("agg_seasons", t0)
    t0 = time.perf_counter()
    con.execute("BEGIN IMMEDIATE")
    con.execute("INSERT INTO weekly_stats (week, user_id, name, games, wins, points)"
                " SELECT week, user_id, MAX(name), COUNT(*), SUM(won), COUNT(*) + 3 * SUM(won) FROM lt_part"
                " WHERE true GROUP BY week, user_id ON CONFLICT(week, user_id) DO UPDATE SET games = games + excluded.games,"
                " wins = wins + excluded.wins, points = points + excluded.points")
    con.execute("INSERT OR IGNORE INTO activity (day, user_id, channel) SELECT DISTINCT day, user_id, 'group' FROM lt_part")
    con.execute("COMMIT")
    phase("agg_weekly_activity", t0)
    con.execute("DROP TABLE lt_part")
    t0 = time.perf_counter()
    con.execute("ANALYZE")
    phase("analyze", t0)
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in (
        "stats", "games", "game_players", "season_stats", "weekly_stats", "activity", "achievements", "clans",
        "clan_members", "fair_play", "referrals", "prefs")}
    print(json.dumps({"timings": timings, "rows": counts}, indent=1))


if __name__ == "__main__":
    main()
