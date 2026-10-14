# Load and correctness test — 1M users, 1M games (2026-10-14)

Run against the **production** database on the owner's request (synthetic ids only: users `9e12+`,
chats `-9e12-`, so the bot never messages them; the owner keeps the data as a permanent fixture).
Backup taken first: `data/backup-pre-loadtest-20261014.db`.

## Tools (`scripts/loadtest/`)

| Script | What it does |
|---|---|
| `sim.py` | Random full games through the real engine; invariants after every step (dead never act, deaths ⇔ chronicle, winner consistent, serialization round trip, disabled roles never dealt). |
| `fuzz.py` | `sim` on all cores, summary of violations and games that never end. |
| `generate.py` | Synthetic users, clans, referrals, achievements and **engine-played** finished games straight into SQLite, timed per phase. |
| `bench_queries.py` | p50/p95/max of every hot `Store` call and the Mini App state on a big database. |
| `concurrency.py` | N groups playing full games at once through the real `App` and handlers, Telegram replaced by a fake with 80 ms latency. Checks lost/double stat updates. |
| `webapp_load.py` | `/api/state` under concurrency with signed initData; 401 for forged/missing/stale, 429 for spam. |

```bash
python -m scripts.loadtest.fuzz --games 1000000
python -m scripts.loadtest.generate --db data/tezmafia.db --users 1000000 --games 1000000
python -m scripts.loadtest.bench_queries --db data/tezmafia.db
python -m scripts.loadtest.concurrency --db data/tezmafia.db --steps 10,100,1000
python -m scripts.loadtest.webapp_load --db data/tezmafia.db
```

## Data volume

1,000,005 users · 1,000,010 games · 9.7M game_players · 4.6M season rows · 4.3M weekly rows ·
8.1M activity rows · 2M achievements · 5,000 clans / 150k members — **9.8 GB**.
Generation: users 4 s, games 229 s (~4,400 games/s incl. engine simulation), aggregates 164 s.

## Findings (before the fixes)

### Logic — 1,000,000 random games, 0 rule violations

| Finding | Share | Fix |
|---|---|---|
| Everybody dead → no winner → the game never ends (the bot loops phases in an empty town) | 0.49 % | `Winner.DRAW` |
| Lone arsonist does not win → never ends | 0.002 % | arsonist wins alone |
| Two survivors nobody can kill (e.g. mage + lucky) | 0.001 % | kept: the vote decides |

After the fix (200k games): 882 draws, 4 two-survivor standoffs, 0 violations.

### Database — p50 at 1M/1M

| Call | Before | Cause |
|---|---|---|
| `active_in_chat`, `load`, `save`, `get_account`, per-message checks | 0.5–3 ms | fine |
| `by_user_lobby_or_live` / `unfinished` (`/start`, role button, watchdog every 60 s) | **1.6 s** | `status != 'finished'` scanned all 1M games |
| `clan_top` | 1.1 s | join over 150k members |
| `season_top` / `top_stats` / `week_top` | 46 / 75 / 23 ms | sort without index |
| `report_since` (daily) | 1.3 s | parsed every payload of the day in Python |
| `delete_user` (`/deletemydata`) | **MemoryError** | loaded every finished game into memory |

### Concurrency — real handlers, 80 ms fake Telegram latency

| Groups at once | Finished | Errors | Lost stat updates | `resolve_night` p50 / p95 |
|---|---|---|---|---|
| 10 | 10/10 | 0 | 0 | 0.5 s / 3.6 s |
| 100 | 95/100 | 37 `database is locked` | 101 players | 2 s / 25 s |
| 1000 | 955/1000 | 502 | 1,170 players | 17 s / 233 s |

Telegram allows ~30 messages/s per bot; 10 parallel games already needed 43 calls/s, so the
real ceiling is Telegram, not the database (~104 calls per game).

### Mini App

~30 req/s ceiling; p50 0.3 s at 10 concurrent, 3.5 s at 100, 17 s at 500; no errors.
Auth refusals and rate limit held under load.

## Fixes (this change)

- **Logic:** draw when nobody is alive; lone arsonist wins.
- **Indexes:** partial `ix_games_active` (active games), stats top/daily/first_seen, season and
  weekly rankings, per-user indexes on season/weekly/activity/quest rows.
- **`delete_user`:** only the user's own games via `game_players`, 200 at a time; `save()` links
  players of every finished game (cancelled too); startup links legacy games once.
- **Rankings cache:** 60 s read-through (`Store.cached`) for `/top`, `/clan top`, `/tournament`,
  `/groupstats` and the Mini App top; off in tests.
- **Daily report:** counters in SQL; prune in batches of 2,000 with their player links.
- **Game end:** all per-player rows in one transaction (`Store.record_game`), every write retried
  on a lock; `busy_timeout` 5 s → 30 s.
- **CPU:** at most 4 result cards rendered at once.
- **Telegram budget:** lobby / vote-board edits merged within 1.5 s, no decorative phase
  reactions, progress news in the result card's caption instead of a second DM.

## After the fixes (same 1M/1M database, commits aecd97c + follow-ups)

### Database — p50

| Call | Before | After |
|---|---|---|
| `by_user_lobby_or_live` / `unfinished` | 1,560 ms | **3 ms** |
| `season_top` (global) / `top_stats` / `week_top` | 46 / 75 / 23 ms | **0.7 / 0.6 / 0.6 ms** |
| `streaks_at_risk` | 75 ms | **0.6 ms** |
| `delete_user` | MemoryError | **34 ms** |
| `report_since` (daily) | 1,272 ms | 534 ms |
| `active_users(30d)` (daily) | 735 ms | 691 ms (33 s before the index pin, see below) |
| Mini App `build_state` | 130 ms | **10 ms** |
| `clan_top` | 1,147 ms | 1,026 ms uncached → served from the 60 s cache |
| `save(game)` (finished) | 2.3 ms | 8.8 ms (now also links players) |

Two regressions showed up only on re-measuring and are fixed: `active_users` picked the new
`ix_activity_user` and scanned 8M rows (33 s) → pinned to the primary key; `clan_stats` took 634 ms
until the planner had statistics → `PRAGMA optimize` at startup and daily (1 ms).

### Concurrency

| Groups at once | Finished | DB errors | Lost stat updates | `resolve_night` p50 / p95 |
|---|---|---|---|---|
| 10 | 10/10 | 0 | 0 | 0.5 s / 2.6 s |
| 100 | 99/100 | **0** (was 37) | **0** (was 101) | 1.9 s / 15 s (was 25 s) |
| 1000 | 999/1000 | **0** (was 502) | **0** (was 1,170) | 17 s / 123 s (was 233 s) |

Telegram calls per game: ~104 → ~94 in this harness (it does not model "message is not modified"
or the merged news DM, which save more in production). The remaining unfinished game per step was a
harness artefact: both runs used the same seed, so chat ids collided with games left by the first run.

Latency above 100 groups is the single process and Telegram itself, not SQLite: the next step is
F7 (server, PostgreSQL, several workers) once the real audience needs it.

### Mini App (60 s cache as in production)

| Concurrent | Before req/s · p50 | After req/s · p50 |
|---|---|---|
| 10 | 32 · 0.31 s | **161 · 0.06 s** |
| 100 | 28 · 3.5 s | **179 · 0.53 s** |
| 500 | 28 · 17 s | **171 · 2.6 s** |

### Found while re-measuring

A deferred lobby edit ran outside the game lock; if Telegram refused the edit it posted a new lobby
and could write back a stale game. It now takes the lock, and "message is not modified" counts as
success (both covered by tests; the race test fails without the lock).
