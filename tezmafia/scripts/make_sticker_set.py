"""Create (or top up) the Raven sticker set from assets/raven/stickers through the bot.

The set belongs to OWNER_ID and is named raven_by_<bot username>, as Bot API requires.
Running it again only adds stickers the set does not have yet.

Usage (from the tezmafia directory, .env provides BOT_TOKEN and OWNER_ID):
    python -m scripts.make_sticker_set
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputSticker

from tezmafia.brand import ASSETS
from tezmafia.config import Settings

STICKERS = ASSETS / "raven" / "stickers"
TITLE = "TezMafia — Qarg‘a"
# File stem → emoji Telegram suggests the sticker for.
EMOJI: dict[str, list[str]] = {
    "s01-hello": ["👋"],
    "s02-suspicious": ["🤨"],
    "s03-shocked": ["😱"],
    "s04-laugh": ["😂"],
    "s05-sleep": ["😴"],
    "s06-vote": ["🗳"],
    "s07-victory": ["🏆"],
    "s08-farewell": ["🥀"],
}


def set_name(bot_username: str) -> str:
    return f"raven_by_{bot_username}"


def sticker_files(folder: Path = STICKERS) -> list[Path]:
    """The WEBP files in emoji order; a missing or unmapped file is an error, not a skip."""
    files = sorted(folder.glob("*.webp"))
    stems = [f.stem for f in files]
    if stems != list(EMOJI):
        raise ValueError(f"sticker files {stems} do not match EMOJI keys {list(EMOJI)}")
    return files


def input_stickers(files: list[Path]) -> list[InputSticker]:
    return [InputSticker(sticker=FSInputFile(f), format="static", emoji_list=EMOJI[f.stem]) for f in files]


async def main() -> None:
    settings = Settings()
    if not settings.owner_id:
        raise SystemExit("OWNER_ID is required: the sticker set needs an owner")
    name = set_name(settings.bot_username)
    files = sticker_files()
    bot = Bot(settings.bot_token)
    try:
        try:
            existing = await bot.get_sticker_set(name)
        except TelegramBadRequest:
            existing = None
        if existing is None:
            await bot.create_new_sticker_set(
                user_id=settings.owner_id, name=name, title=TITLE, stickers=input_stickers(files)
            )
            print(f"created {name} with {len(files)} stickers")
        else:
            have = len(existing.stickers)
            for sticker in input_stickers(files[have:]):
                await bot.add_sticker_to_set(user_id=settings.owner_id, name=name, sticker=sticker)
            print(f"{name}: had {have}, added {max(0, len(files) - have)}")
        final = await bot.get_sticker_set(name)
        print(f"https://t.me/addstickers/{name} — {len(final.stickers)} stickers")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
