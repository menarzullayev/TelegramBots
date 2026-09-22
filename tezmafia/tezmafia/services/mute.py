from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ChatPermissions

from tezmafia.engine import Game

SPEAK = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)

SILENT = ChatPermissions(can_send_messages=False)


async def _restrict(bot: Bot, chat_id: int, user_id: int, perms: ChatPermissions) -> None:
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=perms)
    except TelegramBadRequest:
        return


async def mute_user(bot: Bot, game: Game, user_id: int) -> None:
    await _restrict(bot, game.chat_id, user_id, SILENT)


async def unmute_user(bot: Bot, game: Game, user_id: int) -> None:
    await _restrict(bot, game.chat_id, user_id, SPEAK)


async def apply_phase_mutes(bot: Bot, game: Game, night: bool, enabled: bool) -> None:
    if not enabled:
        return
    try:
        me = await bot.get_chat_member(game.chat_id, (await bot.me()).id)
        if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            return
    except TelegramBadRequest:
        return
    for p in game.players:
        if not p.alive:
            await mute_user(bot, game, p.user_id)
        elif night:
            await mute_user(bot, game, p.user_id)
        else:
            await unmute_user(bot, game, p.user_id)


async def unmute_all(bot: Bot, game: Game) -> None:
    for p in game.players:
        await unmute_user(bot, game, p.user_id)
