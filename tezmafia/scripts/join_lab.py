#!/usr/bin/env python3
"""Join TezMafia Table from handlechecker slots. Never prints sessions."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hc_client import client_for_slot

INVITE = "https://t.me/+49qJubkcO_ZhMTBi"
SLOTS = [7, 8, 15]


async def main() -> None:
    for slot in SLOTS:
        client = client_for_slot(slot)
        async with client:
            me = await client.get_me()
            try:
                chat = await client.join_chat(INVITE)
                print(f"slot {slot} @{me.username} joined {chat.id}")
            except Exception as exc:
                print(f"slot {slot} @{me.username} {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
