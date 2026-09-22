#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hc_client import client_for_slot

PAYLOAD = "/start g_8Xpl5cR0YNc"
SLOTS = [7, 8, 15]


async def main() -> None:
    for slot in SLOTS:
        client = client_for_slot(slot)
        async with client:
            me = await client.get_me()
            await client.send_message("qorashahar_mafia_bot", PAYLOAD)
            print(f"slot {slot} @{me.username} started")


if __name__ == "__main__":
    asyncio.run(main())
