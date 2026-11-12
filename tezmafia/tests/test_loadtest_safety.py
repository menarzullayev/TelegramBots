"""Load tests never write into the live database (scripts/loadtest/safety.py)."""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

from scripts.loadtest import generate
from scripts.loadtest.safety import DEFAULT_DB, ROOT, checked_db

SCRIPTS = ROOT / "scripts" / "loadtest"


@pytest.mark.parametrize("path", ["data/tezmafia.db", "./data/tezmafia.db", str(ROOT / "data" / "tezmafia.db"),
                                  "elsewhere/tezmafia.db"])
def test_live_database_is_refused(path, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="live database"):
        checked_db(path)


def test_database_url_target_is_refused(tmp_path, monkeypatch):
    live = tmp_path / "prod" / "bot.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{live}")
    with pytest.raises(SystemExit, match="live database"):
        checked_db(str(live))


def test_separate_file_is_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert checked_db(DEFAULT_DB) == str((tmp_path / DEFAULT_DB).resolve())
    assert Path(DEFAULT_DB).name != "tezmafia.db"


def test_every_db_script_goes_through_the_guard():
    """A new load-test script with --db must call checked_db too."""
    takes_db = [p for p in SCRIPTS.glob("*.py") if '"--db"' in p.read_text(encoding="utf-8")]
    assert {p.name for p in takes_db} >= {"generate.py", "bench_queries.py", "concurrency.py", "webapp_load.py"}
    for p in takes_db:
        src = p.read_text(encoding="utf-8")
        assert re.search(r"args\.db = checked_db\(args\.db\)", src), f"{p.name} skips checked_db"
        assert "required=True" not in src.split('"--db"', 1)[1].split("\n", 1)[0], f"{p.name}: --db must default"


def test_generate_refuses_live_db_and_leaves_it_untouched(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    live = tmp_path / "data" / "tezmafia.db"
    sqlite3.connect(live).execute("CREATE TABLE stats (user_id INTEGER)").connection.commit()
    before = live.read_bytes()
    monkeypatch.setattr(sys, "argv", ["generate", "--db", "data/tezmafia.db", "--users", "20", "--games", "1"])
    with pytest.raises(SystemExit, match="live database"):
        generate.main()
    assert live.read_bytes() == before


def test_generate_fills_a_fresh_separate_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["generate", "--users", "60", "--games", "12", "--workers", "1"])
    generate.main()
    con = sqlite3.connect(tmp_path / DEFAULT_DB)
    assert con.execute("SELECT COUNT(*) FROM stats WHERE user_id >= ?", (generate.FAKE_USER,)).fetchone()[0] == 60
    assert con.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 12
    assert not (tmp_path / "data" / "tezmafia.db").exists()
