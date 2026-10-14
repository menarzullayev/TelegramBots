"""Keeps the TezMafia bot running on Windows without any console window.

Started by the "TezMafia Bot" scheduled task as `pythonw.exe supervisor.py`. It restarts the bot
after a crash or a kill (that is how a deploy restarts it) and stops only on exit code 75, which
means another copy already polls with this data directory.

Why not PowerShell: under Task Scheduler a hidden console window received close/Ctrl+C events
and took the whole runner down (STATUS_CONTROL_C_EXIT). pythonw has no console at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "data" / "logs"
ALREADY_RUNNING = 75
RESTART_DELAY = 10


def bot_command(root: Path = ROOT) -> list[str]:
    exe = root / ".venv-win" / "Scripts" / "pythonw.exe"
    return [str(exe if exe.exists() else sys.executable), "-m", "tezmafia"]


def log(line: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "runner.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")


def run_once(command: list[str]) -> int:
    env = {**os.environ, "PYTHONUTF8": "1", "LOG_FILE": str(LOGS / "bot.log")}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with open(LOGS / "stderr.log", "ab") as err:
        proc = subprocess.Popen(
            command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
            creationflags=flags,
        )
        return proc.wait()


def main(command: list[str] | None = None, delay: float = RESTART_DELAY, max_runs: int | None = None) -> int:
    command = command or bot_command()
    runs = 0
    while True:
        runs += 1
        log(f"start {command[0]}")
        try:
            code = run_once(command)
        except OSError as exc:
            log(f"launch failed: {exc}")
            code = -1
        log(f"exit {code}")
        if code == ALREADY_RUNNING or (max_runs is not None and runs >= max_runs):
            return code
        time.sleep(delay)


if __name__ == "__main__":
    sys.exit(main())
