#!/usr/bin/env python3
"""Fire /vote <seat> from all handlechecker lab slots at once."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hc_client import client_for_slot

CHAT = -5042113726
SLOTS = [7, 8, 15]


async def one(slot: int, seat: int) -> None:
    client = client_for_slot(slot)
    async with client:
        await client.send_message(CHAT, f"/vote {seat}")
        print(f"slot {slot} /vote {seat}")


async def main() -> None:
    seat = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    await asyncio.gather(*(one(s, seat) for s in SLOTS))


if __name__ == "__main__":
    asyncio.run(main())
