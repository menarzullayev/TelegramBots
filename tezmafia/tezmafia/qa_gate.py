"""Run QA-01..QA-100 and refuse a green board unless all 100 pass."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tezmafia.qa_catalog import TICKETS, assert_complete

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "qa" / "last-run.json"


def main() -> int:
    assert_complete()
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_qa_board.py",
        "-q",
        "--tb=line",
        "--override-ini=addopts=",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed = proc.returncode == 0
    report = {
        "tickets": 100,
        "passed": 100 if passed else 0,
        "failed": 0 if passed else 100,
        "exit": proc.returncode,
        "tail": text[-4000:],
        "board": [
            {
                "id": t["id"],
                "title": t["title"],
                "cat": t["cat"],
                "pri": t["pri"],
                "column": "Done" if passed else "To Do",
            }
            for t in TICKETS
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if not passed:
        sys.stderr.write("QA gate FAILED — 100/100 talab qilinadi.\n")
        return proc.returncode or 1
    sys.stdout.write("QA gate OK — 100/100 passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
