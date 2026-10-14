"""The Windows supervisor restarts the bot after exits and stops on 'already running'."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "supervisor", Path(__file__).resolve().parents[1] / "scripts" / "windows" / "supervisor.py"
)
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)  # type: ignore[union-attr]


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, "LOGS", tmp_path)
    monkeypatch.setattr(supervisor, "ROOT", tmp_path)
    return tmp_path


def test_restarts_after_a_crash(logs) -> None:
    code = supervisor.main([sys.executable, "-c", "raise SystemExit(3)"], delay=0, max_runs=3)
    assert code == 3
    lines = (logs / "runner.log").read_text(encoding="utf-8").splitlines()
    assert sum("start" in line for line in lines) == 3
    assert sum("exit 3" in line for line in lines) == 3


def test_stops_when_another_copy_runs(logs) -> None:
    code = supervisor.main([sys.executable, "-c", "raise SystemExit(75)"], delay=0, max_runs=5)
    assert code == 75
    assert (logs / "runner.log").read_text(encoding="utf-8").count("start") == 1


def test_stderr_is_kept(logs) -> None:
    supervisor.main([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(1)"], delay=0, max_runs=1)
    assert b"boom" in (logs / "stderr.log").read_bytes()


def test_launch_failure_is_logged(logs) -> None:
    assert supervisor.main([str(logs / "missing.exe")], delay=0, max_runs=1) == -1
    assert "launch failed" in (logs / "runner.log").read_text(encoding="utf-8")


def test_prefers_the_venv_pythonw(tmp_path) -> None:
    exe = tmp_path / ".venv-win" / "Scripts" / "pythonw.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert supervisor.bot_command(tmp_path) == [str(exe), "-m", "tezmafia"]
    assert supervisor.bot_command(tmp_path / "none")[0] == sys.executable
