from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    CallbackQuery,
    ChatAdministratorRights,
    FSInputFile,
    InputProfilePhotoStatic,
    InputRichMessage,
    LinkPreviewOptions,
    Message,
    ReactionTypeEmoji,
)

from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.roles import NIGHT_ROLES, ROLE_FACTION, Role
from tezmafia.shop import ROLE_TICKET_COST, resolve_item, resolve_role
from tezmafia.engine import (
    Game,
    Phase,
    begin_lynch,
    begin_night,
    begin_voting,
    can_start,
    cancel,
    extend_lobby,
    join,
    leave,
    mark_dm_ok,
    new_game,
    peek_votes,
    resolve_lynch,
    resolve_night,
    resolve_votes,
    set_lynch_vote,
    set_night_action,
    set_vote,
    start,
)
from tezmafia.emoji import FX
from tezmafia.i18n import LANGS, TG_LANG, cmd, t
from tezmafia.keyboards import chats_kb, host_kb, lang_kb, lobby_kb, lynch_kb, menu_kb, night_kb, roles_kb, shop_kb, vote_kb
from tezmafia.services.mute import apply_phase_mutes, unmute_all
from tezmafia import texts

log = logging.getLogger("tezmafia")
router = Router(name="tezmafia")

ASSETS = Path(__file__).resolve().parent.parent / "assets"
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
RECOVER_GRACE = 30.0


def _photo(name: str) -> FSInputFile | None:
    path = ASSETS / name
    if path.is_file():
        return FSInputFile(path)
    return None


class App:
    def __init__(self, settings: Settings, store: Store, bot: Bot) -> None:
        self.settings = settings
        self.store = store
        self.bot = bot
        self.lock = asyncio.Lock()
        self.timers: dict[str, asyncio.Task[Any]] = {}

    def cfg(self, game: Game | None = None) -> dict[str, Any]:
        s = self.settings
        return {
            "min_players": s.min_players,
            "max_players": s.max_players,
            "mafia_resolve": s.mafia_resolve,
            "reveal_on_death": s.reveal_on_death,
            "first_phase": s.first_phase,
        }

    async def persist(self, game: Game) -> None:
        await self.store.save(game)

    async def lang(self, chat_id: int) -> str:
        return await self.store.get_lang(chat_id)

    def cancel_timer(self, game_id: str) -> None:
        task = self.timers.pop(game_id, None)
        if not task or task.done():
            return
        # finish() runs inside the phase timer; cancelling self drops Game Over.
        if task is asyncio.current_task():
            return
        task.cancel()

    def schedule(self, game_id: str, seconds: float, factory: Callable[[], Awaitable[None]]) -> None:
        self.cancel_timer(game_id)

        async def _run() -> None:
            try:
                await asyncio.sleep(max(0.5, seconds))
                await factory()
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("timer failed game=%s", game_id)

        self.timers[game_id] = asyncio.create_task(_run())

    async def safe_group(self, game: Game, text: str, **kwargs: Any) -> Message | None:
        try:
            return await self.bot.send_message(
                game.chat_id,
                text,
                parse_mode=ParseMode.HTML,
                link_preview_options=NO_PREVIEW,
                **kwargs,
            )
        except (TelegramBadRequest, TelegramRetryAfter, TelegramAPIError):
            log.exception("group send failed chat=%s", game.chat_id)
            return None

    async def safe_photo(self, chat_id: int, name: str, caption: str, **kwargs: Any) -> Message | None:
        photo = _photo(name)
        try:
            if photo:
                return await self.bot.send_photo(
                    chat_id,
                    photo,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    **kwargs,
                )
            return await self.bot.send_message(
                chat_id,
                caption,
                parse_mode=ParseMode.HTML,
                link_preview_options=NO_PREVIEW,
                **kwargs,
            )
        except TelegramAPIError:
            log.exception("photo/send failed chat=%s name=%s", chat_id, name)
            return None

    async def dm(self, user_id: int, text: str, **kwargs: Any) -> bool:
        try:
            await self.bot.send_message(
                user_id,
                text,
                parse_mode=ParseMode.HTML,
                link_preview_options=NO_PREVIEW,
                **kwargs,
            )
            return True
        except (TelegramForbiddenError, TelegramBadRequest):
            return False

    async def react(self, chat_id: int, message_id: int, emoji: str) -> None:
        try:
            await self.bot.set_message_reaction(
                chat_id,
                message_id,
                [ReactionTypeEmoji(emoji=emoji)],
            )
        except TelegramAPIError:
            return

    async def refresh_vote(self, game: Game) -> None:
        if not game.vote_message_id:
            return
        try:
            await self.bot.edit_message_text(
                texts.vote_tally(game, await self.lang(game.chat_id)),
                chat_id=game.chat_id,
                message_id=game.vote_message_id,
                parse_mode=ParseMode.HTML,
                reply_markup=vote_kb(game, await self.lang(game.chat_id)),
                link_preview_options=NO_PREVIEW,
            )
        except TelegramBadRequest:
            pass

    async def refresh_lobby(self, game: Game) -> None:
        lang = await self.lang(game.chat_id)
        text = texts.lobby_text(game, self.settings.bot_username, lang)
        kb = lobby_kb(game, self.settings.bot_username, lang)
        if game.lobby_message_id:
            try:
                await self.bot.edit_message_text(
                    text,
                    chat_id=game.chat_id,
                    message_id=game.lobby_message_id,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                    link_preview_options=NO_PREVIEW,
                )
                return
            except TelegramBadRequest:
                pass
        msg = await self.safe_group(game, text, reply_markup=kb)
        if msg:
            game.lobby_message_id = msg.message_id
            try:
                await self.bot.pin_chat_message(game.chat_id, msg.message_id, disable_notification=True)
            except TelegramBadRequest:
                pass
        await self.persist(game)

    async def apply_loadout(self, game: Game) -> None:
        for p in game.players:
            skip = {"gun"} if p.role and Role(p.role) in NIGHT_ROLES else set()
            flags = await self.store.take_loadout(p.user_id, skip)
            p.shop_shield = flags.get("shield", False)
            p.shop_vote_shield = flags.get("vote_shield", False)
            p.shop_mask = flags.get("mask", False)
            p.shop_fake_id = flags.get("fake_id", False)
            p.shop_gun = flags.get("gun", False)
            p.shop_killer_shield = flags.get("killer_shield", False)

    async def apply_role_tickets(self, game: Game) -> list[tuple[int, str, str]]:
        # DECISION-02 first-wins; DECISION-03 peek only — consume after all DMs.
        claimed: set[str] = set()
        pending: list[tuple[int, str, str]] = []
        for p in game.players:
            want = ((await self.store.get_account(p.user_id)).get("next_role") or "").strip()
            if not want:
                continue
            if p.role == want:
                claimed.add(want)
                pending.append((p.user_id, p.first_name, "claim"))
                continue
            if want in claimed:
                pending.append((p.user_id, p.first_name, "refund"))
                continue
            other = next((x for x in game.players if x.role == want and x.user_id != p.user_id), None)
            if not other:
                pending.append((p.user_id, p.first_name, "refund"))
                continue
            p.role, other.role = other.role, p.role
            p.faction = ROLE_FACTION[Role(p.role)].value
            other.faction = ROLE_FACTION[Role(other.role)].value
            claimed.add(want)
            pending.append((p.user_id, p.first_name, "claim"))
        return pending

    async def commit_role_tickets(self, pending: list[tuple[int, str, str]]) -> None:
        for user_id, first_name, action in pending:
            taken = await self.store.take_next_role(user_id)
            if action == "refund" and taken:
                await self.store.credit_wallet(user_id, first_name, coins=ROLE_TICKET_COST)

    async def start_game(self, game: Game) -> None:
        start(game)
        pending = await self.apply_role_tickets(game)
        await self.persist(game)
        group_lang = await self.lang(game.chat_id)
        banner = await self.safe_photo(game.chat_id, "day.png", texts.roles_public(game, group_lang))
        if banner:
            await self.react(game.chat_id, banner.message_id, "🔒")
        for p in game.players:
            effect = FX["fire"] if p.faction == "mafia" else FX["heart"]
            ok = await self.dm(
                p.user_id,
                texts.role_dm(game, p.user_id, await self.lang(p.user_id)),
                protect_content=True,
                message_effect_id=effect,
            )
            if not ok:
                p.dm_ok = False
        if any(not p.dm_ok for p in game.players):
            await self.safe_group(game, texts.action_reason("dm_pending", group_lang))
            cancel(game)
            await self.persist(game)
            return
        await self.commit_role_tickets(pending)
        await self.apply_loadout(game)
        await self.persist(game)
        if self.settings.first_phase == "night_kill":
            await self.enter_night(game)
        else:
            await self.enter_day(game, from_night=False)

    async def enter_night(self, game: Game) -> None:
        begin_night(game, time.time(), self.settings.night_action_seconds)
        await self.persist(game)
        await apply_phase_mutes(self.bot, game, night=True, enabled=self.settings.mute_night)
        night = await self.safe_photo(game.chat_id, "night.png", texts.night_group(game, await self.lang(game.chat_id)))
        if night:
            await self.react(game.chat_id, night.message_id, "🌙")
        for p in game.alive_players():
            kb = night_kb(game, p.user_id)
            has_action = bool(kb.inline_keyboard)
            await self.dm(
                p.user_id,
                texts.night_prompt(game, p.user_id, has_action, await self.lang(p.user_id)),
                reply_markup=kb if has_action else None,
            )
        self.schedule(
            game.id,
            self.settings.night_action_seconds,
            lambda: self._timed_resolve_night(game.id),
        )

    async def enter_day(self, game: Game, from_night: bool) -> None:
        game.phase = Phase.DAY
        if game.round == 0:
            game.round = 1
        game.deadline = time.time() + self.settings.discussion_seconds
        game.version += 1
        await self.persist(game)
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.settings.mute_night)
        day_lang = await self.lang(game.chat_id)
        caption = (
            texts.day_group(game, self.settings.reveal_on_death, day_lang)
            if from_night
            else texts.day_group(game, False, day_lang)
        )
        banner_name = "death.png" if game.last_death_seat else "day.png"
        day = await self.safe_photo(game.chat_id, banner_name, caption)
        if day:
            await self.react(game.chat_id, day.message_id, "☀️")
        self.schedule(
            game.id,
            self.settings.discussion_seconds,
            lambda: self._timed_begin_vote(game.id),
        )

    async def enter_vote(self, game: Game) -> None:
        begin_voting(game, time.time(), self.settings.voting_seconds)
        await self.persist(game)
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.settings.mute_night)
        vote_lang = await self.lang(game.chat_id)
        msg = await self.safe_group(game, texts.vote_tally(game, vote_lang), reply_markup=vote_kb(game, vote_lang))
        if msg:
            game.vote_message_id = msg.message_id
            await self.persist(game)
        self.schedule(
            game.id,
            self.settings.voting_seconds,
            lambda: self._timed_resolve_vote(game.id),
        )

    async def record_stats(self, game: Game) -> None:
        for p in game.players:
            won = (
                (game.winner == "mafia" and p.faction == "mafia")
                or (game.winner == "town" and p.faction == "town")
                or (game.winner == "maniac" and p.role == "maniac")
                or (game.winner == "suicide" and p.role == "suicide")
                or (game.winner == "arsonist" and p.role == "arsonist")
                or (game.winner == "snitch" and p.role == "snitch")
                or (game.winner == "mage" and p.role == "mage")
                or (game.winner == "crook" and p.role == "crook")
            )
            await self.store.bump_stat(p.user_id, p.first_name, won)

    async def finish(self, game: Game) -> None:
        self.cancel_timer(game.id)
        await self.persist(game)
        try:
            await self.record_stats(game)
        except Exception:
            log.warning("stats failed", exc_info=True)
        over = texts.game_over(game, await self.lang(game.chat_id))
        name = {
            "mafia": "mafia-win.png",
            "town": "town-win.png",
            "maniac": "death.png",
            "suicide": "death.png",
            "arsonist": "death.png",
            "snitch": "death.png",
            "mage": "death.png",
            "crook": "death.png",
        }.get(game.winner or "", "town-win.png")
        short = texts.game_over_short(game, await self.lang(game.chat_id))
        try:
            photo_msg = await asyncio.wait_for(
                self.safe_photo(game.chat_id, name, short),
                timeout=20,
            )
            if photo_msg is None:
                log.warning("game-over photo missing game=%s file=%s", game.id, name)
        except Exception:
            log.exception("game-over photo failed game=%s", game.id)
        await self.safe_group(game, over)
        try:
            await asyncio.wait_for(unmute_all(self.bot, game), timeout=8)
        except Exception:
            log.warning("unmute after finish failed", exc_info=True)

    async def _timed_resolve_night(self, game_id: str) -> None:
        async with self.lock:
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.NIGHT:
                return
            result = resolve_night(game)
            await self.persist(game)
            det = result.get("detective_result")
            if det:
                checked = game.by_seat(det["seat"])
                label = checked.html_label() if checked else f"#{det['seat']}"
                await self.dm(
                    det["detective_id"],
                    texts.detective_result(label, det["is_mafia"], await self.lang(det["detective_id"])),
                    message_effect_id=FX["thumbsup"],
                )
            jour = result.get("journalist_result")
            if jour:
                watched = game.by_seat(jour["seat"])
                label = watched.html_label() if watched else f"#{jour['seat']}"
                names = []
                for seat in jour.get("visitors") or []:
                    v = game.by_seat(seat)
                    names.append(v.html_label() if v else f"#{seat}")
                await self.dm(
                    jour["journalist_id"],
                    texts.journalist_result(
                        label, names, bool(jour.get("helper")), await self.lang(jour["journalist_id"])
                    ),
                    message_effect_id=FX["thumbsup"],
                )
            if result["winner"]:
                await self.finish(game)
                return
            await self.enter_day(game, from_night=True)

    async def _timed_begin_vote(self, game_id: str) -> None:
        async with self.lock:
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.DAY:
                return
            await self.enter_vote(game)

    async def enter_lynch(self, game: Game, seat: int) -> None:
        begin_lynch(game, seat, time.time(), self.settings.lynch_seconds)
        await self.persist(game)
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.settings.mute_night)
        lynch_lang = await self.lang(game.chat_id)
        await self.safe_group(game, texts.lynch_text(game, lynch_lang), reply_markup=lynch_kb(game, lynch_lang))
        self.schedule(
            game.id,
            self.settings.lynch_seconds,
            lambda: self._timed_resolve_lynch(game.id),
        )

    async def _timed_resolve_vote(self, game_id: str) -> None:
        async with self.lock:
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.VOTING:
                return
            seat, tie, _tally = peek_votes(game)
            if seat and not tie:
                await self.enter_lynch(game, seat)
                return
            result = resolve_votes(game)
            await self.persist(game)
            await self.safe_group(
                game,
                texts.elim_group(game, result["tie"], self.settings.reveal_on_death, await self.lang(game.chat_id)),
            )
            if result["winner"]:
                await self.finish(game)
                return
            await self.enter_night(game)

    async def _timed_resolve_lynch(self, game_id: str) -> None:
        async with self.lock:
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.LYNCH:
                return
            result = resolve_lynch(game)
            await self.persist(game)
            await self.safe_group(
                game,
                texts.elim_group(
                    game, not result["confirmed"], self.settings.reveal_on_death, await self.lang(game.chat_id)
                ),
            )
            if result["winner"]:
                await self.finish(game)
                return
            await self.enter_night(game)

    async def _timed_lobby_expire(self, game_id: str) -> None:
        async with self.lock:
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.LOBBY:
                return
            cancel(game)
            await self.persist(game)
            await self.safe_group(game, texts.cancelled(await self.lang(game.chat_id)))

    async def skip_phase(self, game: Game) -> bool:
        if game.phase == Phase.LOBBY:
            ok, _reason = can_start(game)
            if ok:
                await self.start_game(game)
                return True
            return False
        if game.phase == Phase.NIGHT:
            await self._timed_resolve_night(game.id)
            return True
        if game.phase == Phase.DAY:
            await self._timed_begin_vote(game.id)
            return True
        if game.phase == Phase.VOTING:
            await self._timed_resolve_vote(game.id)
            return True
        if game.phase == Phase.LYNCH:
            await self._timed_resolve_lynch(game.id)
            return True
        return False

    async def recover(self) -> None:
        now = time.time()
        timed = {
            Phase.NIGHT: lambda gid: self._timed_resolve_night(gid),
            Phase.DAY: lambda gid: self._timed_begin_vote(gid),
            Phase.VOTING: lambda gid: self._timed_resolve_vote(gid),
            Phase.LYNCH: lambda gid: self._timed_resolve_lynch(gid),
            Phase.LOBBY: lambda gid: self._timed_lobby_expire(gid),
        }
        for game in await self.store.unfinished():
            remain = (game.deadline or now) - now
            factory = timed.get(game.phase)
            if factory:
                if remain <= 0:
                    remain = RECOVER_GRACE
                    game.deadline = now + remain
                    await self.persist(game)
                    log.info("recover grace game=%s phase=%s +%.0fs", game.id, game.phase, remain)
                self.schedule(game.id, remain, lambda gid=game.id, fn=factory: fn(gid))
            elif game.phase == Phase.ROLE_ASSIGNMENT:
                async with self.lock:
                    fresh = await self.store.load(game.id)
                    if fresh and fresh.phase == Phase.ROLE_ASSIGNMENT:
                        await self.enter_night(fresh)
            log.info("recovered game=%s phase=%s", game.id, game.phase)


app: App


async def _lang(chat_id: int) -> str:
    return await app.lang(chat_id)


def _is_group(message: Message) -> bool:
    return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


@router.message(Command("mafia", "newgame", "game"))
async def cmd_mafia(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        await message.answer("O‘yinni guruhda /mafia bilan oching.")
        return
    async with app.lock:
        existing = await app.store.active_in_chat(message.chat.id)
        if existing and existing.phase != Phase.FINISHED:
            await app.refresh_lobby(existing) if existing.phase == Phase.LOBBY else await message.answer(
                f"Bu guruhda o‘yin bor ({existing.phase})."
            )
            return
        game = new_game(message.chat.id, message.from_user.id, **app.cfg())
        join(game, message.from_user.id, message.from_user.first_name, message.from_user.username)
        game.deadline = time.time() + app.settings.lobby_seconds
        await app.persist(game)
        await app.refresh_lobby(game)
        app.schedule(
            game.id,
            app.settings.lobby_seconds,
            lambda gid=game.id: app._timed_lobby_expire(gid),
        )


@router.message(Command("join"))
async def cmd_join(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.lock:
        game = await app.store.active_in_chat(message.chat.id)
        if not game or game.phase != Phase.LOBBY:
            await message.answer(t(await _lang(message.chat.id), "extend.no_lobby"))
            return
        ok, reason = join(game, message.from_user.id, message.from_user.first_name, message.from_user.username)
        await app.persist(game)
        if not ok and reason == "full":
            await message.answer(texts.action_reason("full", await _lang(message.chat.id)))
            return
        await app.refresh_lobby(game)
        if not game.by_user(message.from_user.id) or not game.by_user(message.from_user.id).dm_ok:
            await message.answer(
                f"DM oching: https://t.me/{app.settings.bot_username}?start=g_{game.id}",
                link_preview_options=NO_PREVIEW,
            )


@router.message(Command("cancel", "stopmafia", "stop"))
async def cmd_cancel(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.lock:
        game = await app.store.active_in_chat(message.chat.id)
        lang = await _lang(message.chat.id)
        if not game:
            await message.answer(t(lang, "status.none"))
            return
        if message.from_user.id not in {game.host_id, app.settings.owner_id}:
            await message.answer(t(lang, "cancel.host_only"))
            return
        app.cancel_timer(game.id)
        cancel(game)
        await unmute_all(app.bot, game)
        await app.persist(game)
        await message.answer(texts.cancelled(lang))


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not _is_group(message):
        lang = await _lang(message.chat.id)
        game = await app.store.by_user_lobby_or_live(message.from_user.id) if message.from_user else None
        if not game:
            await message.answer(t(lang, "status.none"))
            return
        await message.answer(t(lang, "status.phase", phase=game.phase, n=len(game.alive_players())))
        return
    lang = await _lang(message.chat.id)
    game = await app.store.active_in_chat(message.chat.id)
    if not game:
        await message.answer(t(lang, "status.none"))
        return
    if game.phase == Phase.LOBBY:
        await app.refresh_lobby(game)
        return
    await message.answer(t(lang, "status.live", phase=game.phase, round=game.round, n=len(game.alive_players())))


@router.message(Command("roles"))
async def cmd_roles(message: Message) -> None:
    lang = await _lang(message.chat.id)
    await message.answer(texts.roles_catalog(lang), reply_markup=roles_kb(lang))


@router.callback_query(F.data.startswith("hr:"))
async def cb_role_card(query: CallbackQuery) -> None:
    if not query.data:
        return
    key = query.data.split(":", 1)[1]
    await query.answer()
    if query.message:
        lang = await _lang(query.message.chat.id)
        await query.message.answer(texts.role_card(key, lang))


@router.message(Command("leave"))
async def cmd_leave(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.lock:
        game = await app.store.active_in_chat(message.chat.id)
        if not game or game.phase != Phase.LOBBY:
            await message.answer(t(await _lang(message.chat.id), "leave.not_lobby"))
            return
        leave(game, message.from_user.id)
        await app.persist(game)
        await app.refresh_lobby(game)
        await message.answer(t(await _lang(message.chat.id), "leave.ok"))


@router.message(Command("extend", "prolong"))
async def cmd_extend(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.lock:
        game = await app.store.active_in_chat(message.chat.id)
        if not game:
            await message.answer(t(await _lang(message.chat.id), "extend.no_lobby"))
            return
        lang = await _lang(message.chat.id)
        ok, reason = extend_lobby(game, app.settings.extend_seconds, app.settings.max_extends)
        if not ok:
            await message.answer(texts.action_reason(reason, lang))
            return
        await app.persist(game)
        remain = max(1.0, (game.deadline or time.time()) - time.time())
        app.schedule(game.id, remain, lambda gid=game.id: app._timed_lobby_expire(gid))
        await message.answer(texts.extended(app.settings.extend_seconds, lang))


@router.message(Command("next"))
async def cmd_next(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    game = await app.store.active_in_chat(message.chat.id)
    if not game:
        await message.answer(t(await _lang(message.chat.id), "status.none"))
        return
    lang = await _lang(message.chat.id)
    if message.from_user.id not in {game.host_id, app.settings.owner_id}:
        await message.answer(t(lang, "next.host_only"))
        return
    if await app.skip_phase(game):
        await message.answer(texts.next_phase(lang))
    else:
        await message.answer(
            texts.start_reason("too_few", lang) if game.phase == Phase.LOBBY else texts.action_reason("not_night", lang)
        )


@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
    rows = await app.store.top_stats()
    await message.answer(texts.top_text(rows, await _lang(message.chat.id)))


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    if not message.from_user:
        return
    acc = await app.store.get_account(message.from_user.id)
    await message.answer(
        texts.profile_text(
            acc["name"] or message.from_user.first_name,
            acc["games"],
            acc["wins"],
            acc["coins"],
            acc["gems"],
            acc["inventory"],
            acc.get("next_role", ""),
            lang=await _lang(message.chat.id),
        )
    )


@router.message(Command("shop"))
async def cmd_shop(message: Message) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    acc = await app.store.get_account(message.from_user.id)
    await message.answer(
        texts.shop_text(acc["coins"], acc["gems"], acc["inventory"], lang),
        reply_markup=shop_kb(lang),
    )


@router.message(Command("buy"))
async def cmd_buy(message: Message, command: CommandObject) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    raw = (command.args or "").strip()
    if not raw:
        await message.answer(t(lang, "buy.usage"))
        return
    low = raw.lower()
    if low.startswith("role ") or low.startswith("rol "):
        role = resolve_role(raw.split(None, 1)[1])
        if not role:
            await message.answer(texts.action_reason("no_item", lang))
            return
        ok, reason = await app.store.buy_next_role(
            message.from_user.id, message.from_user.first_name, role
        )
        await message.answer(texts.action_reason("bought" if ok else reason, lang))
        if ok:
            acc = await app.store.get_account(message.from_user.id)
            await message.answer(
                texts.profile_text(
                    acc["name"] or message.from_user.first_name,
                    acc["games"],
                    acc["wins"],
                    acc["coins"],
                    acc["gems"],
                    acc["inventory"],
                    acc.get("next_role", ""),
                    lang=lang,
                )
            )
        return
    key = resolve_item(raw)
    if not key:
        await message.answer(texts.action_reason("no_item", lang))
        return
    ok, reason = await app.store.buy_item(
        message.from_user.id, message.from_user.first_name, key
    )
    await message.answer(texts.action_reason("bought" if ok else reason, lang))
    if ok:
        acc = await app.store.get_account(message.from_user.id)
        await message.answer(
            texts.shop_text(acc["coins"], acc["gems"], acc["inventory"], lang),
            reply_markup=shop_kb(lang),
        )


@router.message(Command("chats", "enter"))
async def cmd_chats(message: Message) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    games = await app.store.games_for_user(message.from_user.id)
    await message.answer(
        texts.chats_text(len(games), lang),
        reply_markup=chats_kb(games, app.settings.bot_username, lang),
    )


@router.message(Command("settings", "lang"))
async def cmd_settings(message: Message) -> None:
    lang = await app.store.get_lang(message.chat.id)
    await message.answer(texts.settings_text(lang), reply_markup=lang_kb(lang))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    lang = await _lang(message.chat.id)
    rich_ok = False
    try:
        await message.bot.send_rich_message(
            message.chat.id,
            InputRichMessage(html=texts.help_html(lang)),
        )
        rich_ok = True
    except TelegramAPIError:
        pass
    await message.answer(
        t(lang, "btn.shortcuts") if rich_ok else texts.help_text(lang),
        link_preview_options=NO_PREVIEW,
        reply_markup=menu_kb(lang),
    )


@router.message(Command("startgame"))
async def cmd_startgame(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.lock:
        game = await app.store.active_in_chat(message.chat.id)
        lang = await _lang(message.chat.id)
        if not game:
            await message.answer(t(lang, "extend.no_lobby"))
            return
        if message.from_user.id != game.host_id:
            await message.answer(t(lang, "startgame.host_only"))
            return
        ok, reason = can_start(game)
        if not ok:
            await message.answer(texts.start_reason(reason, lang))
            return
        await app.start_game(game)


@router.message(Command("action"))
async def cmd_action(message: Message, command: CommandObject) -> None:
    if not message.from_user or message.chat.type != ChatType.PRIVATE:
        return
    try:
        seat = int((command.args or "").strip())
    except ValueError:
        await message.answer(t(await _lang(message.chat.id), "action.usage"))
        return
    lang = await _lang(message.chat.id)
    async with app.lock:
        game = await app.store.by_user_lobby_or_live(message.from_user.id)
        if not game:
            await message.answer(t(lang, "no_game"))
            return
        ok, reason = set_night_action(game, message.from_user.id, seat)
        if not ok:
            await message.answer(texts.action_reason(reason, lang))
            return
        await app.persist(game)
        target = game.by_seat(seat)
        await message.answer(texts.picked(target.html_label() if target else str(seat), lang))


@router.message(Command("vote"))
async def cmd_vote(message: Message, command: CommandObject) -> None:
    if not message.from_user:
        return
    try:
        seat = int((command.args or "").strip())
    except ValueError:
        await message.answer(t(await _lang(message.chat.id), "vote.usage"))
        return
    lang = await _lang(message.chat.id)
    async with app.lock:
        game = (
            await app.store.active_in_chat(message.chat.id)
            if _is_group(message)
            else await app.store.by_user_lobby_or_live(message.from_user.id)
        )
        if not game:
            await message.answer(t(lang, "no_game"))
            return
        ok, reason = set_vote(game, message.from_user.id, seat)
        if not ok:
            await message.answer(texts.action_reason(reason, lang))
            return
        await app.persist(game)
        target = game.by_seat(seat)
        await app.refresh_vote(game)
        await message.answer(texts.voted(target.html_label() if target else str(seat), lang))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    if not message.from_user:
        return
    payload = (command.args or "").strip()
    if message.chat.type != ChatType.PRIVATE:
        await cmd_mafia(message)
        return
    lang = await _lang(message.chat.id)
    if not payload.startswith("g_"):
        await message.answer(
            texts.host_menu_text(lang),
            link_preview_options=NO_PREVIEW,
            reply_markup=host_kb(app.settings.bot_username, lang),
        )
        return
    game_id = payload[2:]
    async with app.lock:
        game = await app.store.load(game_id)
        if not game:
            await message.answer(t(lang, "start.not_found"))
            return
        if game.phase == Phase.LOBBY:
            join(game, message.from_user.id, message.from_user.first_name, message.from_user.username)
        player = game.by_user(message.from_user.id)
        if not player:
            await message.answer(t(lang, "start.not_in"))
            return
        mark_dm_ok(game, message.from_user.id)
        await app.persist(game)
        await message.answer(texts.dm_opened(lang), message_effect_id=FX["thumbsup"])
        if game.phase == Phase.LOBBY:
            await app.refresh_lobby(game)


@router.callback_query(F.data.startswith("s:"))
async def cb_start(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    game_id = query.data.split(":", 1)[1]
    async with app.lock:
        game = await app.store.load(game_id)
        lang = await _lang(query.from_user.id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        if query.from_user.id != game.host_id:
            await query.answer(t(lang, "cb.host_only"), show_alert=True)
            return
        ok, reason = can_start(game)
        if not ok:
            await query.answer(texts.start_reason(reason, lang), show_alert=True)
            return
        await query.answer(t(lang, "cb.starting"))
        await app.start_game(game)


@router.callback_query(F.data.startswith("l:"))
async def cb_leave(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    game_id = query.data.split(":", 1)[1]
    async with app.lock:
        game = await app.store.load(game_id)
        lang = await _lang(query.from_user.id)
        if not game or game.phase != Phase.LOBBY:
            await query.answer(t(lang, "cb.lobby_closed"), show_alert=True)
            return
        leave(game, query.from_user.id)
        await app.persist(game)
        await query.answer(t(lang, "leave.ok"))
        await app.refresh_lobby(game)


@router.callback_query(F.data.regexp(r"^n[a-z]:"))
async def cb_night(query: CallbackQuery) -> None:
    if not query.from_user or not query.data or query.message is None:
        return
    if query.message.chat.type != ChatType.PRIVATE:
        await query.answer(t(await _lang(query.from_user.id), "cb.dm_only"), show_alert=True)
        return
    prefix, game_id, seat_s = query.data.split(":")
    lang = await _lang(query.from_user.id)
    async with app.lock:
        game = await app.store.load(game_id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        kind = "shoot" if prefix == "ns" else ""
        ok, reason = set_night_action(game, query.from_user.id, int(seat_s), kind=kind)
        if not ok:
            await query.answer(texts.action_reason(reason, lang), show_alert=True)
            return
        await app.persist(game)
        target = game.by_seat(int(seat_s))
        await query.answer(texts.picked(target.html_label() if target else seat_s, lang))


@router.callback_query(F.data.startswith("v:"))
async def cb_vote(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    _, game_id, seat_s = query.data.split(":")
    async with app.lock:
        game = await app.store.load(game_id)
        lang = await _lang(query.from_user.id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        ok, reason = set_vote(game, query.from_user.id, int(seat_s))
        if not ok:
            await query.answer(texts.action_reason(reason, lang), show_alert=True)
            return
        await app.persist(game)
        target = game.by_seat(int(seat_s))
        await app.refresh_vote(game)
        await query.answer(texts.voted(target.html_label() if target else seat_s, lang), show_alert=False)


@router.callback_query(F.data.startswith("vx:"))
async def cb_vote_clear(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    game_id = query.data.split(":", 1)[1]
    async with app.lock:
        game = await app.store.load(game_id)
        lang = await _lang(query.from_user.id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        ok, reason = set_vote(game, query.from_user.id, None)
        if not ok:
            await query.answer(texts.action_reason(reason, lang), show_alert=True)
            return
        await app.persist(game)
        await app.refresh_vote(game)
        await query.answer(texts.action_reason("cleared", lang))


@router.callback_query(F.data.startswith("ly:"))
async def cb_lynch(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    _prefix, game_id, bit = query.data.split(":")
    async with app.lock:
        game = await app.store.load(game_id)
        lang = await _lang(query.from_user.id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        ok, reason = set_lynch_vote(game, query.from_user.id, bit == "1")
        if not ok:
            await query.answer(texts.action_reason(reason, lang), show_alert=True)
            return
        await app.persist(game)
        await query.answer(t(lang, "cb.yes" if bit == "1" else "cb.no"))


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(query: CallbackQuery) -> None:
    if not query.data or not query.message:
        return
    lang = query.data.split(":", 1)[1]
    saved = await app.store.set_lang(query.message.chat.id, lang)
    await query.answer(texts.lang_switched(saved))
    await query.message.answer(texts.lang_switched(saved))


@router.callback_query(F.data.startswith("m:"))
async def cb_menu(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    action = query.data.split(":", 1)[1]
    await query.answer()
    if not query.message:
        return
    lang = await _lang(query.message.chat.id)
    if action == "profile":
        acc = await app.store.get_account(query.from_user.id)
        await query.message.answer(
            texts.profile_text(
                acc["name"] or query.from_user.first_name,
                acc["games"],
                acc["wins"],
                acc["coins"],
                acc["gems"],
                acc["inventory"],
                acc.get("next_role", ""),
                lang=lang,
            )
        )
        return
    if action == "shop":
        acc = await app.store.get_account(query.from_user.id)
        await query.message.answer(
            texts.shop_text(acc["coins"], acc["gems"], acc["inventory"], lang),
            reply_markup=shop_kb(lang),
        )
        return
    if action == "roles":
        await query.message.answer(texts.roles_catalog(lang), reply_markup=roles_kb(lang))
        return
    if action == "lang":
        await query.message.answer(texts.settings_text(lang), reply_markup=lang_kb(lang))
        return
    if action == "chats":
        games = await app.store.games_for_user(query.from_user.id)
        await query.message.answer(
            texts.chats_text(len(games), lang),
            reply_markup=chats_kb(games, app.settings.bot_username, lang),
        )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    lang = await _lang(query.from_user.id)
    item_key = query.data.split(":", 1)[1]
    ok, reason = await app.store.buy_item(query.from_user.id, query.from_user.first_name, item_key)
    await query.answer(texts.action_reason(reason if not ok else "bought", lang), show_alert=True)
    if query.message:
        acc = await app.store.get_account(query.from_user.id)
        try:
            await query.message.edit_text(
                texts.shop_text(acc["coins"], acc["gems"], acc["inventory"], lang),
                reply_markup=shop_kb(lang),
            )
        except TelegramAPIError:
            pass


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def night_delete(message: Message) -> None:
    if not message.from_user or message.from_user.is_bot:
        return
    if message.text and message.text.startswith("/"):
        return
    game = await app.store.active_in_chat(message.chat.id)
    if not game or game.phase != Phase.NIGHT:
        return
    try:
        await message.delete()
    except TelegramAPIError:
        return


def _bot_command_lists(lang: str) -> tuple[list[BotCommand], list[BotCommand], list[BotCommand]]:
    default = [
        BotCommand(command="mafia", description=cmd(lang, "mafia")),
        BotCommand(command="join", description=cmd(lang, "join")),
        BotCommand(command="leave", description=cmd(lang, "leave")),
        BotCommand(command="extend", description=cmd(lang, "extend")),
        BotCommand(command="next", description=cmd(lang, "next")),
        BotCommand(command="status", description=cmd(lang, "status")),
        BotCommand(command="roles", description=cmd(lang, "roles")),
        BotCommand(command="profile", description=cmd(lang, "profile")),
        BotCommand(command="shop", description=cmd(lang, "shop")),
        BotCommand(command="buy", description=cmd(lang, "buy")),
        BotCommand(command="top", description=cmd(lang, "top")),
        BotCommand(command="settings", description=cmd(lang, "settings")),
        BotCommand(command="stop", description=cmd(lang, "stop")),
        BotCommand(command="help", description=cmd(lang, "help")),
    ]
    group = [
        BotCommand(command="game", description=cmd(lang, "game")),
        BotCommand(command="join", description=cmd(lang, "join")),
        BotCommand(command="leave", description=cmd(lang, "leave")),
        BotCommand(command="extend", description=cmd(lang, "extend")),
        BotCommand(command="next", description=cmd(lang, "next")),
        BotCommand(command="status", description=cmd(lang, "status")),
        BotCommand(command="stop", description=cmd(lang, "stop")),
        BotCommand(command="help", description=cmd(lang, "help")),
    ]
    private = [
        BotCommand(command="start", description=cmd(lang, "start")),
        BotCommand(command="help", description=cmd(lang, "help")),
        BotCommand(command="profile", description=cmd(lang, "profile")),
        BotCommand(command="shop", description=cmd(lang, "shop")),
        BotCommand(command="buy", description=cmd(lang, "buy")),
        BotCommand(command="roles", description=cmd(lang, "roles")),
        BotCommand(command="status", description=cmd(lang, "status_dm")),
    ]
    return default, group, private


async def _sync_bot_commands(bot: Bot) -> None:
    keys = (
        "mafia", "game", "join", "leave", "extend", "next", "status", "status_dm",
        "roles", "profile", "shop", "buy", "top", "settings", "stop", "help", "start",
    )
    digest = hashlib.sha1(
        json.dumps({lang: {k: cmd(lang, k) for k in keys} for lang in LANGS}, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:12]
    marker = Path("data") / f".commands_{digest}"
    if marker.exists():
        return
    scopes = (
        (BotCommandScopeDefault(), 0),
        (BotCommandScopeAllGroupChats(), 1),
        (BotCommandScopeAllPrivateChats(), 2),
    )
    try:
        for lang, tg in [("uz", None), *TG_LANG.items()]:
            lists = _bot_command_lists(lang)
            for scope, idx in scopes:
                kwargs: dict = {"scope": scope}
                if tg:
                    kwargs["language_code"] = tg
                await bot.set_my_commands(lists[idx], **kwargs)
        Path("data").mkdir(exist_ok=True)
        for old in Path("data").glob(".commands_*"):
            if old != marker:
                old.unlink(missing_ok=True)
        marker.write_text(digest + "\n", encoding="utf-8")
    except TelegramRetryAfter as exc:
        log.warning("setMyCommands flood retry_after=%s", getattr(exc, "retry_after", "?"))
    except Exception:
        log.warning("setMyCommands skipped", exc_info=True)


async def assert_polling_contract(bot: Bot) -> None:
    """DECISION-01/10: refuse to poll if a webhook already owns updates."""
    info = await bot.get_webhook_info()
    url = getattr(info, "url", "") or ""
    if url:
        host = url.split("/")[2] if "://" in url else "set"
        raise RuntimeError(f"DECISION-10: webhook attached ({host}); polling contract broken")


async def setup_bot_profile(bot: Bot) -> None:
    marker = Path("data/.profile_ok")
    if not marker.exists():
        try:
            await bot.set_my_name("TezMafia")
            await bot.set_my_short_description("Qora shahar. Guruhda klassik Mafia.")
            await bot.set_my_description(
                "TezMafia — guruhda klassik Mafia. Bot hakam: tun/kun, DM rollar, ovoz, mute. "
                "5–16 o‘yinchi. Guruhda /mafia, keyin Join + DM ochish, host Start."
            )
            marker.parent.mkdir(exist_ok=True)
            marker.write_text("ok\n", encoding="utf-8")
        except Exception:
            log.warning("profile texts skipped (flood or reject)", exc_info=True)
    await _sync_bot_commands(bot)
    await bot.set_my_default_administrator_rights(
        ChatAdministratorRights(
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=False,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=True,
            can_post_stories=False,
            can_edit_stories=False,
            can_delete_stories=False,
            can_send_welcome_messages=False,
            can_pin_messages=True,
            can_manage_topics=False,
        )
    )
    pic = _photo("avatar.jpg") or _photo("avatar.png")
    if pic:
        try:
            await bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=pic))
        except Exception:
            log.warning("profile photo rejected", exc_info=True)


async def run() -> None:
    global app
    settings = Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    store = Store(settings.database_url)
    await store.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    app = App(settings, store, bot)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await setup_bot_profile(bot)
    except Exception:
        log.exception("setup_bot_profile failed; continuing to poll")
    await app.recover()
    await assert_polling_contract(bot)
    log.info(
        "DECISION-01 runtime=single-node store=sqlite polling=on lock=in-process bot=@%s",
        settings.bot_username,
    )
    log.info("polling as @%s", settings.bot_username)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
