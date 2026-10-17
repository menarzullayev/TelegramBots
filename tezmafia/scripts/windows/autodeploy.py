"""Auto-deploy on the production PC: when origin/main moves and its CI is green, pull, restart, verify.

Runs hidden as the "TezMafia AutoDeploy" scheduled task (pythonw). Cloud sessions merge PRs; this is the only
thing that touches the live bot. Steps and outcomes go to data/logs/autodeploy.log; a failed deploy DMs the owner
once per commit. The supervisor restarts the bot after we stop it, so a deploy is: pull, stop, wait for /health to
report the new commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .../tezmafia
REPO = ROOT.parent
LOGS = ROOT / "data" / "logs"
STATE = ROOT / "data" / "autodeploy.json"
HEALTH = "http://127.0.0.1:8796/health"
INTERVAL = 90
HEALTH_TIMEOUT = 150
CI_NAME = "pytest + QA gate"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(line: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "autodeploy.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")


def sh(*cmd: str, cwd: Path = REPO, timeout: int = 300) -> str:
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
    if out.returncode:
        raise RuntimeError(f"{' '.join(cmd)}: {out.stderr.strip() or out.stdout.strip()}")
    return out.stdout.strip()


def decide(head: str, remote: str, touches_bot: bool, ci: str) -> str:
    """What to do with origin/main: idle | pull (docs/other projects only) | wait | skip | deploy."""
    if head == remote:
        return "idle"
    if not touches_bot:
        return "pull"
    return {"success": "deploy", "pending": "wait", "none": "wait"}.get(ci, "skip")


def ci_state(sha: str) -> str:
    """success | pending | failure | none for the TezMafia CI check of a commit (via the gh CLI)."""
    raw = sh("gh", "api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs", "--jq",
             f'[.check_runs[] | select(.name == "{CI_NAME}") | {{status, conclusion}}]')
    runs = json.loads(raw or "[]")
    if not runs:
        return "none"
    if any(r["status"] != "completed" for r in runs):
        return "pending"
    return "success" if all(r["conclusion"] == "success" for r in runs) else "failure"


def env_value(key: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def notify(text: str) -> None:
    token, owner = env_value("BOT_TOKEN"), env_value("OWNER_ID")
    if not (token and owner):
        return
    data = urllib.parse.urlencode({"chat_id": owner, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20).read()
    except OSError as exc:
        log(f"notify failed: {exc!r}")


def health_commit() -> str:
    try:
        with urllib.request.urlopen(HEALTH, timeout=5) as r:
            return json.loads(r.read()).get("commit", "")
    except (OSError, ValueError):
        return ""


def stop_bot() -> None:
    # The bot runs as pythonw.exe (venv launcher + base interpreter); match the command line, not the name.
    sh("powershell", "-NoProfile", "-Command",
       "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '-m tezmafia\"?\\s*$' } | "
       "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state), encoding="utf-8")


def step(state: dict) -> None:
    sh("git", "fetch", "-q", "origin", "main")
    head, remote = sh("git", "rev-parse", "HEAD"), sh("git", "rev-parse", "origin/main")
    if head == remote:
        return
    changed = sh("git", "diff", "--name-only", head, remote).splitlines()
    touches_bot = any(p.startswith("tezmafia/") for p in changed)
    ci = ci_state(remote) if touches_bot else "none"
    action = decide(head, remote, touches_bot, ci)
    if action == "wait":
        return
    if action == "skip":
        if state.get("failed") != remote:
            log(f"skip {remote[:7]}: CI {ci}")
            notify(f"⚠️ TezMafia: {remote[:7]} not deployed, CI is {ci}.")
            state["failed"] = remote
            save_state(state)
        return
    sh("git", "pull", "--ff-only", "-q", "origin", "main")
    if action == "pull":
        log(f"pulled {remote[:7]} (no bot changes, no restart)")
        return
    if "tezmafia/pyproject.toml" in changed:
        sh(str(ROOT / ".venv-win" / "Scripts" / "python.exe"), "-m", "pip", "install", "-q", "-e", ".", cwd=ROOT)
    log(f"deploy {head[:7]} -> {remote[:7]}")
    stop_bot()
    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        time.sleep(5)
        if remote.startswith(health_commit() or "-"):
            log(f"live {remote[:7]}")
            state.pop("failed", None)
            save_state(state)
            return
    log(f"health check failed for {remote[:7]}")
    notify(f"❌ TezMafia: deployed {remote[:7]} but /health does not report it after {HEALTH_TIMEOUT}s. Check data/logs.")
    state["failed"] = remote
    save_state(state)


def main() -> int:
    state = load_state()
    log("autodeploy started")
    while True:
        try:
            step(state)
        except Exception as exc:  # keep the loop alive; a broken step is logged and retried next round
            log(f"error: {exc!r}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
