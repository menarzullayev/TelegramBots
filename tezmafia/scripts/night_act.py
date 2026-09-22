#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hc_client import client_for_slot

SLOTS = [7, 8, 15]


async def main() -> None:
    for slot in SLOTS:
        client = client_for_slot(slot)
        async with client:
            me = await client.get_me()
            async for msg in client.get_chat_history("qorashahar_mafia_bot", limit=4):
                text = msg.text or ""
                markup = msg.reply_markup
                data = ""
                if markup and getattr(markup, "inline_keyboard", None):
                    data = markup.inline_keyboard[0][0].callback_data or ""
                if data.startswith("nm:"):
                    await client.send_message("qorashahar_mafia_bot", "/action 1")
                    print(f"slot {slot} @{me.username} mafia -> /action 1")
                    break
            else:
                print(f"slot {slot} @{me.username} no mafia action")


if __name__ == "__main__":
    asyncio.run(main())
