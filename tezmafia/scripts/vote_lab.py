#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hc_client import client_for_slot

CHAT = -5042113726
# town votes 5 (likely mafia); slot 15 is mafia and votes 2
VOTES = {7: 5, 8: 5, 15: 2}


async def main() -> None:
    for slot, seat in VOTES.items():
        client = client_for_slot(slot)
        async with client:
            me = await client.get_me()
            await client.send_message(CHAT, f"/vote {seat}")
            print(f"slot {slot} @{me.username} /vote {seat}")


if __name__ == "__main__":
    asyncio.run(main())
