#!/usr/bin/env python3
"""Join competitor lobby from handlechecker slots. Never prints sessions."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hc_client import client_for_slot


async def one(slot: int, start_payload: str, bot: str) -> None:
    client = client_for_slot(slot)
    async with client:
        me = await asyncio.wait_for(client.get_me(), timeout=20)
        await asyncio.wait_for(client.send_message(bot, f"/start {start_payload}"), timeout=20)
        print(f"slot {slot} @{me.username} started {bot}")


def _argv(raw: list[str]) -> list[str]:
    """`--payload -100…` is a flag to argparse; glue it as --payload=-100…"""
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "--payload" and i + 1 < len(raw):
            out.append("--payload=" + raw[i + 1])
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return out


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bot", default="TrueMafiaBot")
    p.add_argument("--payload", required=True, help="Use --payload=-100CHAT_0 for MafiaAz")
    p.add_argument("--slots", default="7")
    args = p.parse_args(_argv(sys.argv[1:]))
    for slot in [int(x) for x in args.slots.split(",") if x.strip()]:
        try:
            await asyncio.wait_for(one(slot, args.payload, args.bot), timeout=45)
        except Exception as exc:
            print(f"slot {slot} {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
