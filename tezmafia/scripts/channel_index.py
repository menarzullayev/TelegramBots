"""Plain-text table of contents for the channel.

Rich messages show "Please open Telegram" on the t.me/s web view and in channel catalogs, so one plain
HTML message lists every post with a link to it. Web visitors and catalogs then see real content.

    python -m scripts.channel_index --chat -1003743103312 [--username tezmafia] [--dry-run] [--edit ID]
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "channel"
SERIES = {
    "A": "🚪 Tanishuv",
    "B": "🎭 Rollar",
    "C": "🛠 Guruh adminlari uchun",
    "D": "🏙 O‘yinchi hayoti",
    "E": "💎 Bozor va to‘lovlar",
    "F": "🔬 Parda ortida",
}
LIMIT = 4096  # Telegram counts the text without the HTML tags


def link(chat: int, username: str | None, message_id: int) -> str:
    if username:
        return f"https://t.me/{username}/{message_id}"
    return f"https://t.me/c/{str(chat).removeprefix('-100')}/{message_id}"


def build(posts: list[dict], sent: dict, chat: int, username: str | None) -> str:
    lines = [
        "<b>TezMafia — Qorashahar kanali mundarijasi</b>",
        "Guruhingiz uchun bepul Mafiya hakami: rollar, tun va ovoz berish — hammasi avtomatik. "
        "Botni guruhga qo‘shing: @qorashahar_mafia_bot",
    ]
    for code, title in SERIES.items():
        items = [p for p in posts if p["series"] == code and str(p["id"]) in sent]
        if not items:
            continue
        lines.append("")
        lines.append(f"<b>{title}</b>")
        for p in items:
            url = link(chat, username, sent[str(p["id"])]["post"])
            lines.append(f"• <a href=\"{url}\">{html.escape(p['uz']['title'])}</a>")
    lines += ["", "🇷🇺 Русский и 🇬🇧 English — внутри каждого поста / inside every post.", "#mundarija"]
    return "\n".join(lines)


def visible_length(text: str) -> int:
    import re

    return len(html.unescape(re.sub(r"<[^>]+>", "", text)))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--username", help="public channel username for t.me links")
    ap.add_argument("--edit", type=int, help="edit this message id instead of sending a new one")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    posts = sorted((json.loads(f.read_text(encoding="utf-8")) for f in (ROOT / "posts").glob("*.json")),
                   key=lambda p: p["id"])
    sent = json.loads((ROOT / ".state" / f"{args.chat}.json").read_text(encoding="utf-8"))
    text = build(posts, sent, args.chat, args.username)
    size = visible_length(text)
    if size > LIMIT:
        raise SystemExit(f"index is {size} characters, over the {LIMIT} limit")
    if args.dry_run:
        print(text)
        print(f"\n{size}/{LIMIT} characters")
        return

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    from tezmafia.config import Settings

    bot = Bot(Settings().bot_token, default=DefaultBotProperties(parse_mode="HTML", link_preview_is_disabled=True))
    try:
        if args.edit:
            await bot.edit_message_text(text, chat_id=args.chat, message_id=args.edit)
            print(f"edited {args.edit}")
        else:
            msg = await bot.send_message(args.chat, text, disable_notification=True)
            print(f"sent {msg.message_id}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
