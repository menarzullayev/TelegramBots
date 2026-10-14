from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatPermissions

from tezmafia.engine import Game

log = logging.getLogger("tezmafia")

# Fallback when the group's own default permissions cannot be read.
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
    # A failed mute must never stop the game: the phase timer is already armed.
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=perms)
    except TelegramAPIError:
        log.debug("restrict skipped chat=%s user=%s", chat_id, user_id, exc_info=True)


async def _speak(bot: Bot, chat_id: int) -> ChatPermissions:
    """The group's default member permissions, so unmuting never grants more than the group allows."""
    try:
        chat = await bot.get_chat(chat_id)
    except TelegramAPIError:
        return SPEAK
    return chat.permissions or SPEAK


async def mute_user(bot: Bot, game: Game, user_id: int) -> None:
    await _restrict(bot, game.chat_id, user_id, SILENT)


async def unmute_user(bot: Bot, game: Game, user_id: int, perms: ChatPermissions | None = None) -> None:
    await _restrict(bot, game.chat_id, user_id, perms or await _speak(bot, game.chat_id))


async def apply_phase_mutes(bot: Bot, game: Game, night: bool, enabled: bool) -> None:
    if not enabled:
        return
    try:
        me = await bot.get_chat_member(game.chat_id, (await bot.me()).id)
        if me.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            return
    except TelegramAPIError:
        return
    speak: ChatPermissions | None = None
    for p in game.players:
        if not p.alive or night:
            await mute_user(bot, game, p.user_id)
        else:
            speak = speak or await _speak(bot, game.chat_id)
            await unmute_user(bot, game, p.user_id, speak)


async def unmute_all(bot: Bot, game: Game) -> None:
    speak = await _speak(bot, game.chat_id)
    for p in game.players:
        await unmute_user(bot, game, p.user_id, speak)
