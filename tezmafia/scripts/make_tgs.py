#!/usr/bin/env python3
"""Minimal Telegram animated stickers (TGS = gzipped Lottie, 512 canvas)."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

DST = Path("/home/nsn/Workspace/TelegramBots/tezmafia/assets/stickers")


def lottie(name: str, color: list[float], kind: str) -> dict:
    # color is RGB 0..1
    r, g, b = color
    if kind == "pulse":
        shape = {
            "ty": "el",
            "p": {"a": 0, "k": [256, 256]},
            "s": {
                "a": 1,
                "k": [
                    {"t": 0, "s": [220, 220], "i": {"x": [0.5], "y": [1]}, "o": {"x": [0.5], "y": [0]}},
                    {"t": 45, "s": [340, 340], "i": {"x": [0.5], "y": [1]}, "o": {"x": [0.5], "y": [0]}},
                    {"t": 90, "s": [220, 220]},
                ],
            },
        }
    else:
        shape = {
            "ty": "rc",
            "p": {"a": 0, "k": [256, 256]},
            "s": {"a": 0, "k": [280, 280]},
            "r": {
                "a": 1,
                "k": [
                    {"t": 0, "s": [20]},
                    {"t": 90, "s": [80]},
                ],
            },
        }
    return {
        "v": "5.7.4",
        "fr": 30,
        "ip": 0,
        "op": 90,
        "w": 512,
        "h": 512,
        "nm": name,
        "ddd": 0,
        "assets": [],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 4,
                "nm": name,
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100},
                    "r": {
                        "a": 1,
                        "k": [
                            {"t": 0, "s": [0]},
                            {"t": 90, "s": [180 if kind == "spin" else 0]},
                        ],
                    },
                    "p": {"a": 0, "k": [256, 256, 0]},
                    "a": {"a": 0, "k": [256, 256, 0]},
                    "s": {"a": 0, "k": [100, 100, 100]},
                },
                "ao": 0,
                "shapes": [
                    {
                        "ty": "gr",
                        "it": [
                            shape,
                            {"ty": "st", "c": {"a": 0, "k": [r, g, b, 1]}, "o": {"a": 0, "k": 100}, "w": {"a": 0, "k": 14}},
                            {"ty": "fl", "c": {"a": 0, "k": [r, g, b, 1]}, "o": {"a": 0, "k": 35}},
                            {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}},
                        ],
                    }
                ],
                "ip": 0,
                "op": 90,
                "st": 0,
            }
        ],
    }


def write_tgs(name: str, data: dict) -> None:
    raw = json.dumps(data, separators=(",", ":")).encode()
    out = DST / f"{name}.tgs"
    with gzip.open(out, "wb", compresslevel=9) as fh:
        fh.write(raw)
    print(out, out.stat().st_size)


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    write_tgs("night", lottie("night", [0.55, 0.08, 0.12], "pulse"))
    write_tgs("day", lottie("day", [0.85, 0.68, 0.28], "pulse"))
    write_tgs("vote", lottie("vote", [0.75, 0.75, 0.78], "spin"))
    write_tgs("town", lottie("town", [0.35, 0.72, 0.45], "pulse"))
    write_tgs("mafia", lottie("mafia", [0.7, 0.1, 0.12], "spin"))


if __name__ == "__main__":
    main()
