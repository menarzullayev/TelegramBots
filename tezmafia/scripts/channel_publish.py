"""Publish the channel launch series (channel/posts/*.json) as Telegram rich messages.

    python -m scripts.channel_publish --chat -1003743103312 [--ids 1-18] [--edit] [--dry-run]

Each post becomes one rich message built from Bot API 10.x blocks: photo or slideshow on top, the
Uzbek title and text, collapsed Russian and English sections (details blocks), inline buttons and a
hashtag footer. A native poll follows when the post has one. Images are uploaded once and reused by
file_id (cache in channel/.state/media.json); sent message ids are kept per chat in
channel/.state/<chat>.json so `--edit` updates the drafts in place instead of posting duplicates.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    FSInputFile,
    InputMediaPhoto,
    InputPollOption,
    InputRichBlockBlockQuotation,
    InputRichBlockButtons,
    InputRichBlockDetails,
    InputRichBlockFooter,
    InputRichBlockList,
    InputRichBlockListItem,
    InputRichBlockParagraph,
    InputRichBlockPhoto,
    InputRichBlockSectionHeading,
    InputRichBlockSlideshow,
    InputRichBlockTable,
    InputRichMessage,
    RichBlockTableCell,
    RichMessageButton,
    RichTextBold,
    RichTextCode,
    RichTextItalic,
    RichTextUrl,
)

from tezmafia.brand import ASSETS

ROOT = Path(__file__).resolve().parent.parent / "channel"
STATE = ROOT / ".state"
ALLOWED_URL = re.compile(r"^https://(t\.me/qorashahar_mafia_bot(\?start(group)?=[\w-]*)?|mafia\.bugvector\.uz/?)$")
INLINE = re.compile(r"\*\*(.+?)\*\*|_(.+?)_|\[(.+?)\]\((https?://[^)\s]+)\)|`([^`]+)`")
LANGS = (("ru", "🇷🇺 Русский"), ("en", "🇬🇧 English"))


def rich(text: str) -> Any:
    """`**bold**`, `_italic_`, `[label](url)` and `` `code` `` → a rich text value (plain str when unformatted)."""
    parts: list[Any] = []
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            parts.append(text[pos : m.start()])
        bold, italic, label, url, code = m.groups()
        if bold is not None:
            parts.append(RichTextBold(text=bold))
        elif italic is not None:
            parts.append(RichTextItalic(text=italic))
        elif label is not None:
            parts.append(RichTextUrl(text=label, url=url))
        else:
            parts.append(RichTextCode(text=code))
        pos = m.end()
    if pos < len(text):
        parts.append(text[pos:])
    return parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts


def blocks_of(items: list[dict]) -> list[Any]:
    out: list[Any] = []
    for b in items:
        if "p" in b:
            out.append(InputRichBlockParagraph(text=rich(b["p"])))
        elif "h" in b:
            out.append(InputRichBlockSectionHeading(text=rich(b["h"]), size=3))
        elif "list" in b:
            out.append(InputRichBlockList(
                items=[InputRichBlockListItem(blocks=[InputRichBlockParagraph(text=rich(x))]) for x in b["list"]]))
        elif "quote" in b:
            out.append(InputRichBlockBlockQuotation(blocks=[InputRichBlockParagraph(text=rich(b["quote"]))]))
        elif "table" in b:
            rows = b["table"]
            out.append(InputRichBlockTable(
                cells=[[RichBlockTableCell(align="left", valign="middle", text=rich(str(c)), is_header=(i == 0))
                        for c in row] for i, row in enumerate(rows)],
                is_bordered=True, is_striped=True))
        else:
            raise ValueError(f"unknown block {b}")
    return out


async def call(coro_fn):
    """Run a Bot API call, waiting out flood limits (channels allow roughly 20 messages a minute)."""
    for _ in range(8):
        try:
            return await coro_fn()
        except TelegramRetryAfter as e:
            print(f"  flood wait {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 1)
    raise RuntimeError("still rate limited after 8 waits")


class Media:
    """Upload each image once (to the target chat, then delete the carrier message) and reuse its file_id."""

    def __init__(self, bot: Bot, chat: int) -> None:
        self.bot, self.chat = bot, chat
        self.path = STATE / "media.json"
        self.cache: dict[str, str] = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}

    async def file_id(self, key: str, file: Path) -> str:
        if key not in self.cache:
            msg = await call(lambda: self.bot.send_photo(self.chat, FSInputFile(file), disable_notification=True))
            self.cache[key] = msg.photo[-1].file_id
            await asyncio.sleep(1.5)
            await call(lambda: self.bot.delete_message(self.chat, msg.message_id))
            await asyncio.sleep(1.5)
            STATE.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(self.cache, indent=1), encoding="utf-8")
        return self.cache[key]

    async def visual(self, post: dict) -> list[str]:
        v = post.get("visual") or {}
        if v.get("type") in ("image", "slideshow"):
            return [await self.file_id(p, ASSETS / "raven" / p) for p in v.get("images", [])]
        if v.get("type") == "mock":
            from scripts.channel_mock import render

            key = "mock:" + hashlib.sha1(json.dumps(v["mock"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if key not in self.cache:
                with tempfile.TemporaryDirectory() as tmp:
                    out = Path(tmp) / "mock.jpg"
                    render(v["mock"]).save(out, "JPEG", quality=88, optimize=True)
                    return [await self.file_id(key, out)]
            return [self.cache[key]]
        return []


def build(post: dict, photos: list[str]) -> InputRichMessage:
    blocks: list[Any] = []
    if len(photos) == 1:
        blocks.append(InputRichBlockPhoto(photo=InputMediaPhoto(media=photos[0])))
    elif photos:
        blocks.append(InputRichBlockSlideshow(blocks=[InputRichBlockPhoto(photo=InputMediaPhoto(media=f)) for f in photos]))
    blocks.append(InputRichBlockSectionHeading(text=rich(post["uz"]["title"]), size=2))
    blocks += blocks_of(post["uz"]["blocks"])
    for lang, label in LANGS:
        if post.get(lang):
            inner = [InputRichBlockSectionHeading(text=rich(post[lang]["title"]), size=3), *blocks_of(post[lang]["blocks"])]
            blocks.append(InputRichBlockDetails(summary=label, blocks=inner))
    buttons = []
    for b in post.get("buttons") or []:
        if not ALLOWED_URL.match(b["url"]):
            raise ValueError(f"post {post['id']}: url not allowed {b['url']}")
        buttons.append(RichMessageButton(text=b["uz"], url=b["url"]))
    if buttons:
        blocks.append(InputRichBlockButtons(buttons=buttons))
    tags = " ".join(post.get("hashtags") or [])
    blocks.append(InputRichBlockFooter(text=f"{tags} · @qorashahar_mafia_bot".strip(" ·")))
    return InputRichMessage(blocks=blocks)


async def send_poll(bot: Bot, chat: int, poll: dict) -> int:
    q, opts = poll["question"]["uz"], [o["uz"] for o in poll["options"]]
    kw: dict[str, Any] = {}
    if poll.get("type") == "quiz":
        kw.update(type="quiz", correct_option_ids=poll.get("correct", [0]))
        if poll.get("explanation"):
            kw["explanation"] = poll["explanation"]["uz"][:200]
    msg = await bot.send_poll(chat, q[:300], [InputPollOption(text=o[:100]) for o in opts], is_anonymous=True, **kw)
    return msg.message_id


def load(ids: set[int] | None) -> list[dict]:
    posts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "posts").glob("*.json"))]
    posts.sort(key=lambda p: p["id"])
    return [p for p in posts if ids is None or p["id"] in ids]


def parse_ids(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out |= set(range(int(a), int(b or a) + 1))
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--ids")
    ap.add_argument("--edit", action="store_true", help="edit already-sent posts in place")
    ap.add_argument("--dry-run", action="store_true", help="build every message, send nothing")
    args = ap.parse_args()
    posts = load(parse_ids(args.ids))
    if args.dry_run:
        for p in posts:
            build(p, ["dummy"] * len((p.get("visual") or {}).get("images", [])))
        print(f"{len(posts)} posts build fine")
        return

    from tezmafia.config import Settings

    bot = Bot(Settings().bot_token)
    STATE.mkdir(exist_ok=True)
    state_file = STATE / f"{args.chat}.json"
    sent: dict[str, Any] = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
    media = Media(bot, args.chat)
    try:
        for post in posts:
            key = str(post["id"])
            message = build(post, await media.visual(post))
            for _attempt in range(5):
                try:
                    if args.edit and key in sent:
                        await bot.edit_message_text(chat_id=args.chat, message_id=sent[key]["post"], rich_message=message)
                        print(f"edited  #{post['id']:02d} {post['slug']}")
                    elif key not in sent:
                        msg = await bot.send_rich_message(args.chat, message, disable_notification=True)
                        entry = {"post": msg.message_id}
                        if post.get("poll"):
                            await asyncio.sleep(1.5)
                            entry["poll"] = await send_poll(bot, args.chat, post["poll"])
                        sent[key] = entry
                        print(f"sent    #{post['id']:02d} {post['slug']}")
                    else:
                        print(f"skip    #{post['id']:02d} (already sent; use --edit)")
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
            state_file.write_text(json.dumps(sent, indent=1), encoding="utf-8")
            await asyncio.sleep(4)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
