#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

SRC = Path("/home/nsn/.cursor/projects/home-nsn/assets")
DST = Path("/home/nsn/Workspace/TelegramBots/tezmafia/assets")

MAP = {
    "tezmafia-avatar.png": "avatar.png",
    "tezmafia-night.png": "night.png",
    "tezmafia-day.png": "day.png",
    "tezmafia-death.png": "death.png",
    "tezmafia-town-win.png": "town-win.png",
    "tezmafia-mafia-win.png": "mafia-win.png",
}


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in MAP.items():
        src = SRC / src_name
        if src.is_file():
            shutil.copy2(src, DST / dst_name)
            print("copied", dst_name, src.stat().st_size)


if __name__ == "__main__":
    main()
