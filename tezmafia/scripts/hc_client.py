"""Handlechecker slot client helper. Never prints session strings."""
from __future__ import annotations

import sys
from pathlib import Path

HC_ROOT = Path("/home/nsn/Telegram/handlechecker")
HC_SRC = HC_ROOT / "src"
HC_SITE = HC_ROOT / ".venv/lib/python3.12/site-packages"
for path in (HC_SITE, HC_SRC):
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))


def client_for_slot(slot: int):
    from handlechecker.config import get_settings
    from handlechecker.telegram.session_store import session_string_for_slot
    from pyrogram import Client

    settings = get_settings()
    session = session_string_for_slot(slot)
    if not session:
        raise RuntimeError(f"slot {slot} empty")
    return Client(
        name=f"tezmafia_slot_{slot}",
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
        session_string=session,
        in_memory=True,
    )
