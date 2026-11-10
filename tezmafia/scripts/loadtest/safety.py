"""Load tests run against their own database file, never the bot's live one.

The 2026-10-14 run wrote 1M users and 1M games into data/tezmafia.db; 9.8 GB of synthetic rows (and inflated
counters on the real accounts that shared groups with them) stayed in production for a month. Every script that
takes --db goes through checked_db(), which refuses the live file, so a test database is always a separate file
that can simply be deleted afterwards.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = "data/loadtest.db"
LIVE_NAME = "tezmafia.db"


def live_paths() -> set[Path]:
    """The database the bot itself would open here: its default and DATABASE_URL, if set."""
    paths = {(ROOT / "data" / LIVE_NAME).resolve(), (Path.cwd() / "data" / LIVE_NAME).resolve()}
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite") and ":///" in url:
        raw = url.split(":///", 1)[1].split("?", 1)[0]
        if raw and raw != ":memory:":
            paths.add(Path(raw).resolve())
    return paths


def checked_db(path: str) -> str:
    """Absolute path of a load-test database; exits if it is (or looks like) the live one."""
    target = Path(path).resolve()
    if target in live_paths() or target.name == LIVE_NAME:
        raise SystemExit(
            f"refusing to load-test {target}: that is the bot's live database. "
            f"Use a separate file, e.g. --db {DEFAULT_DB}, and delete it when done."
        )
    return str(target)


def ensure_schema(path: str) -> None:
    """Create the bot's tables in a new test database (the generator inserts into existing tables)."""
    from tezmafia.db import Store

    async def run() -> None:
        store = Store(f"sqlite+aiosqlite:///{path}")
        await store.init()
        await store.engine.dispose()

    asyncio.run(run())
