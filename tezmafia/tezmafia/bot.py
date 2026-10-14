from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    CallbackQuery,
    ChatAdministratorRights,
    ChatMemberUpdated,
    EphemeralMessageParameters,
    ErrorEvent,
    FSInputFile,
    InputProfilePhotoStatic,
    InputRichMessage,
    LinkPreviewOptions,
    Message,
    ReactionTypeEmoji,
)

from tezmafia import texts
from tezmafia.brand import ASSETS, caption_fits, media, role_card, win_media
from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.emoji import FX
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
from tezmafia.i18n import LANGS, TG_LANG, cmd, phase_label, t
from tezmafia.keyboards import (
    chats_kb,
    delete_kb,
    host_kb,
    lang_kb,
    lobby_kb,
    lynch_kb,
    menu_kb,
    my_role_kb,
    night_kb,
    roles_kb,
    shop_kb,
    vote_kb,
)
from tezmafia.roles import NIGHT_ROLES, ROLE_FACTION, Role
from tezmafia.services.analytics import ActivityMiddleware
from tezmafia.services.mute import apply_phase_mutes, unmute_all
from tezmafia.services.runtime import Alerter, ChatLocks, InstanceLock, RetryAfterMiddleware
from tezmafia.shop import ROLE_TICKET_COST, resolve_item, resolve_role

log = logging.getLogger("tezmafia")
router = Router(name="tezmafia")

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
RECOVER_GRACE = 30.0
ALREADY_RUNNING = 75


def _photo(name: str) -> FSInputFile | None:
    path = ASSETS / name
    if path.is_file():
        return FSInputFile(path)
    return None


async def _answer_with_photo(message: Message, name: str | None, text: str, **kwargs: Any) -> Message:
    """Reply with a picture on top; falls back to a plain reply when the photo cannot be sent."""
    preview = kwargs.pop("link_preview_options", NO_PREVIEW)
    photo = _photo(name) if name else None
    if photo:
        try:
            if caption_fits(text):
                return await message.answer_photo(photo, caption=text, **kwargs)
            await message.answer_photo(photo)
        except TelegramAPIError:
            log.warning("menu photo failed chat=%s name=%s", message.chat.id, name, exc_info=True)
    return await message.answer(text, link_preview_options=preview, **kwargs)


class App:
    def __init__(self, settings: Settings, store: Store, bot: Bot) -> None:
        self.settings = settings
        self.store = store
        self.bot = bot
        self.locks = ChatLocks()
        self.timers: dict[str, asyncio.Task[Any]] = {}
        self._chat_of: dict[str, int] = {}
        self.alerts = Alerter(bot, settings.owner_id)

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
        self._chat_of[game.id] = game.chat_id
        await self.store.save(game)

    @asynccontextmanager
    async def game_lock(self, game_id: str) -> AsyncIterator[None]:
        """Lock of the chat a game lives in; handlers then reload the game under it."""
        chat_id = self._chat_of.get(game_id)
        if chat_id is None:
            game = await self.store.load(game_id)
            chat_id = game.chat_id if game else 0
            if game:
                self._chat_of[game_id] = chat_id
        async with self.locks(chat_id):
            yield

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
            except Exception as exc:
                log.exception("timer failed game=%s", game_id)
                await self.alerts.send(f"timer:{type(exc).__name__}", f"⚠️ Taymer xatosi, o'yin {game_id}: {exc!r}")

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
            if photo and caption_fits(caption):
                return await self.bot.send_photo(
                    chat_id,
                    photo,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    **kwargs,
                )
            if photo:
                # Too long for a caption: the picture goes first, the text keeps its own message.
                await self.bot.send_photo(chat_id, photo, protect_content=kwargs.get("protect_content"))
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
        except TelegramAPIError:
            # Network hiccup or a flood wait longer than the middleware absorbs: try once more.
            log.warning("dm failed user=%s, retrying once", user_id, exc_info=True)
            await asyncio.sleep(1)
            try:
                await self.bot.send_message(
                    user_id, text, parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW, **kwargs
                )
                return True
            except TelegramAPIError:
                return False

    async def dm_photo(self, user_id: int, name: str | None, text: str, **kwargs: Any) -> bool:
        """DM with a picture; any failure other than a closed DM falls back to the plain text DM."""
        photo = _photo(name) if name else None
        if not photo:
            return await self.dm(user_id, text, **kwargs)
        try:
            if caption_fits(text):
                await self.bot.send_photo(user_id, photo, caption=text, parse_mode=ParseMode.HTML, **kwargs)
                return True
            await self.bot.send_photo(user_id, photo, protect_content=kwargs.get("protect_content"))
        except TelegramForbiddenError:
            return False
        except TelegramAPIError:
            log.warning("dm photo failed user=%s name=%s", user_id, name, exc_info=True)
        return await self.dm(user_id, text, **kwargs)

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

    async def send_role_dms(self, game: Game) -> bool:
        """Role card to every player; False when at least one DM is closed."""
        for p in game.players:
            effect = FX["fire"] if p.faction == "mafia" else FX["heart"]
            ok = await self.dm_photo(
                p.user_id,
                role_card(p.role or ""),
                texts.role_dm(game, p.user_id, await self.lang(p.user_id)),
                protect_content=True,
                message_effect_id=effect,
            )
            if not ok:
                p.dm_ok = False
        return all(p.dm_ok for p in game.players)

    async def unpin_lobby(self, game: Game) -> None:
        if not game.lobby_message_id:
            return
        try:
            await self.bot.unpin_chat_message(game.chat_id, message_id=game.lobby_message_id)
        except TelegramAPIError:
            pass

    async def start_game(self, game: Game) -> None:
        start(game)
        pending = await self.apply_role_tickets(game)
        await self.persist(game)
        await self.unpin_lobby(game)
        group_lang = await self.lang(game.chat_id)
        banner = await self.safe_photo(game.chat_id, media("roles_dealt"), texts.roles_public(game, group_lang))
        if banner:
            await self.react(game.chat_id, banner.message_id, "🔒")
        if not await self.send_role_dms(game):
            await self.safe_group(game, texts.start_reason("dm_pending", group_lang))
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
        self.schedule(game.id, self.settings.night_action_seconds, lambda: self._timed_resolve_night(game.id))
        await apply_phase_mutes(self.bot, game, night=True, enabled=self.settings.mute_night)
        group_lang = await self.lang(game.chat_id)
        night = await self.safe_photo(
            game.chat_id, media("night"), texts.night_group(game, group_lang), reply_markup=my_role_kb(game, group_lang)
        )
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

    async def enter_day(self, game: Game, from_night: bool) -> None:
        game.phase = Phase.DAY
        if game.round == 0:
            game.round = 1
        game.deadline = time.time() + self.settings.discussion_seconds
        game.version += 1
        await self.persist(game)
        self.schedule(game.id, self.settings.discussion_seconds, lambda: self._timed_begin_vote(game.id))
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.settings.mute_night)
        day_lang = await self.lang(game.chat_id)
        caption = (
            texts.day_group(game, self.settings.reveal_on_death, day_lang)
            if from_night
            else texts.day_group(game, False, day_lang)
        )
        banner_name = media("dawn_death") if game.last_death_seat else media("dawn")
        day = await self.safe_photo(game.chat_id, banner_name, caption, reply_markup=my_role_kb(game, day_lang))
        if day:
            await self.react(game.chat_id, day.message_id, "☀️")

    async def enter_vote(self, game: Game) -> None:
        begin_voting(game, time.time(), self.settings.voting_seconds)
        await self.persist(game)
        self.schedule(game.id, self.settings.voting_seconds, lambda: self._timed_resolve_vote(game.id))
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.settings.mute_night)
        vote_lang = await self.lang(game.chat_id)
        msg = await self.safe_group(game, texts.vote_tally(game, vote_lang), reply_markup=vote_kb(game, vote_lang))
        if msg:
            game.vote_message_id = msg.message_id
            await self.persist(game)

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
        name = win_media(game.winner)
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
        await self.send_summary(game, over)
        try:
            await asyncio.wait_for(unmute_all(self.bot, game), timeout=8)
        except Exception:
            log.warning("unmute after finish failed", exc_info=True)

    async def send_summary(self, game: Game, fallback: str) -> None:
        """Final roles as a rich-message table; the classic text if the client API rejects it."""
        try:
            await self.bot.send_rich_message(
                game.chat_id, InputRichMessage(html=texts.game_over_rich(game, await self.lang(game.chat_id)))
            )
        except (TelegramAPIError, AttributeError):
            log.info("rich summary unavailable, sending text game=%s", game.id, exc_info=True)
            await self.safe_group(game, fallback)

    async def _timed_resolve_night(self, game_id: str) -> None:
        async with self.game_lock(game_id):
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
        async with self.game_lock(game_id):
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.DAY:
                return
            await self.enter_vote(game)

    async def enter_lynch(self, game: Game, seat: int) -> None:
        begin_lynch(game, seat, time.time(), self.settings.lynch_seconds)
        await self.persist(game)
        self.schedule(game.id, self.settings.lynch_seconds, lambda: self._timed_resolve_lynch(game.id))
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.settings.mute_night)
        lynch_lang = await self.lang(game.chat_id)
        await self.safe_photo(
            game.chat_id,
            media("verdict_confirm"),
            texts.lynch_text(game, lynch_lang),
            reply_markup=lynch_kb(game, lynch_lang),
        )

    async def _timed_resolve_vote(self, game_id: str) -> None:
        async with self.game_lock(game_id):
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.VOTING:
                return
            seat, tie, _tally = peek_votes(game)
            if seat and not tie:
                await self.enter_lynch(game, seat)
                return
            result = resolve_votes(game)
            await self.persist(game)
            await self.safe_photo(
                game.chat_id,
                media("trial"),
                texts.elim_group(game, result["tie"], self.settings.reveal_on_death, await self.lang(game.chat_id)),
            )
            if result["winner"]:
                await self.finish(game)
                return
            await self.enter_night(game)

    async def _timed_resolve_lynch(self, game_id: str) -> None:
        async with self.game_lock(game_id):
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.LYNCH:
                return
            result = resolve_lynch(game)
            await self.persist(game)
            verdict = texts.elim_group(
                game, not result["confirmed"], self.settings.reveal_on_death, await self.lang(game.chat_id)
            )
            if result["confirmed"]:
                await self.safe_photo(game.chat_id, media("verdict_sealed"), verdict)
            else:
                await self.safe_group(game, verdict)
            if result["winner"]:
                await self.finish(game)
                return
            await self.enter_night(game)

    async def _timed_lobby_expire(self, game_id: str) -> None:
        async with self.game_lock(game_id):
            game = await self.store.load(game_id)
            if not game or game.phase != Phase.LOBBY:
                return
            cancel(game)
            await self.persist(game)
            await self.unpin_lobby(game)
            await self.safe_group(game, texts.cancelled(await self.lang(game.chat_id)))

    async def skip_phase(self, game: Game) -> bool:
        if game.phase == Phase.LOBBY:
            async with self.game_lock(game.id):
                fresh = await self.store.load(game.id)
                if not fresh or fresh.phase != Phase.LOBBY or not can_start(fresh)[0]:
                    return False
                await self.start_game(fresh)
                return True
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

    def phase_timer(self, phase: str) -> Callable[[str], Awaitable[None]] | None:
        """The handler that ends a timed phase, or None for phases without a deadline."""
        return {
            Phase.NIGHT: self._timed_resolve_night,
            Phase.DAY: self._timed_begin_vote,
            Phase.VOTING: self._timed_resolve_vote,
            Phase.LYNCH: self._timed_resolve_lynch,
            Phase.LOBBY: self._timed_lobby_expire,
        }.get(phase)

    async def recover(self) -> None:
        now = time.time()
        for game in await self.store.unfinished():
            self._chat_of[game.id] = game.chat_id
            remain = (game.deadline or now) - now
            factory = self.phase_timer(game.phase)
            if factory:
                if remain <= 0:
                    remain = RECOVER_GRACE
                    game.deadline = now + remain
                    await self.persist(game)
                    log.info("recover grace game=%s phase=%s +%.0fs", game.id, game.phase, remain)
                self.schedule(game.id, remain, lambda gid=game.id, fn=factory: fn(gid))
            elif game.phase == Phase.ROLE_ASSIGNMENT:
                # Crashed between dealing roles and the first night: DMs may be missing, so resend them.
                # Role tickets of that start are not charged (their claims were only in memory).
                async with self.game_lock(game.id):
                    fresh = await self.store.load(game.id)
                    if fresh and fresh.phase == Phase.ROLE_ASSIGNMENT:
                        if not await self.send_role_dms(fresh):
                            cancel(fresh)
                            await self.persist(fresh)
                            await self.safe_group(fresh, texts.start_reason("dm_pending", await self.lang(fresh.chat_id)))
                        else:
                            await self.apply_loadout(fresh)
                            await self.enter_night(fresh)
            log.info("recovered game=%s phase=%s", game.id, game.phase)

    async def daily_report(self) -> str:
        r = await self.store.report_since(time.time() - 86400)
        pruned = await self.store.prune_finished(self.settings.retention_days)
        await self.store.prune_activity()
        yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        month = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))
        dau = await self.store.active_users(yesterday)
        mau = await self.store.active_users(month)
        mau_dm = await self.store.active_users(month, "dm")
        return (
            "📊 TezMafia, oxirgi 24 soat\n"
            f"O'yinlar: {r['games']} (bekor: {r['cancelled']}), guruhlar: {r['chats']}\n"
            f"O'yinchilar: {r['players']}, yangi: {r['new_users']}, jami: {r['users']}\n"
            f"Faol: kun {dau} · 30 kun {mau} (DM orqali {mau_dm})\n"
            f"Hozir ochiq stollar: {r['live']}\n"
            f"Tozalangan eski o'yinlar: {pruned}"
        )

    async def daily_report_loop(self) -> None:
        while True:
            now = time.localtime()
            target = time.mktime((*now[:3], self.settings.report_hour, 0, 0, 0, 0, -1))
            if target <= time.time():
                target += 86400
            await asyncio.sleep(target - time.time())
            try:
                await self.alerts.send(f"report:{time.strftime('%Y-%m-%d')}", await self.daily_report())
            except Exception:
                log.exception("daily report failed")

    async def watchdog_pass(self, slack: float = 45.0) -> list[str]:
        """Re-arm games whose deadline passed with no live timer (lost task, crash mid-phase)."""
        now = time.time()
        rearmed: list[str] = []
        for game in await self.store.unfinished():
            task = self.timers.get(game.id)
            factory = self.phase_timer(game.phase)
            if not factory or (task and not task.done()):
                continue
            if (game.deadline or now) + slack > now:
                continue
            self._chat_of[game.id] = game.chat_id
            log.warning("watchdog re-armed game=%s phase=%s", game.id, game.phase)
            self.schedule(game.id, 1.0, lambda gid=game.id, fn=factory: fn(gid))
            rearmed.append(game.id)
            await self.alerts.send(
                f"stuck:{game.id}", f"⚠️ Qotib qolgan o'yin qayta ishga tushirildi: {game.id} ({game.phase})"
            )
        return rearmed

    async def watchdog(self, interval: float = 60.0) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await self.watchdog_pass()
            except Exception:
                log.exception("watchdog pass failed")


app: App


def _build_label() -> str:
    """Short git commit of the running code, for the owner's startup alert."""
    head = Path(__file__).resolve().parents[2] / ".git" / "HEAD"
    try:
        ref = head.read_text(encoding="utf-8").strip()
        if ref.startswith("ref: "):
            ref = (head.parent / ref[5:]).read_text(encoding="utf-8").strip()
        return ref[:7]
    except OSError:
        return "unknown"


async def _lang(chat_id: int) -> str:
    return await app.lang(chat_id)


def _is_group(message: Message) -> bool:
    return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


def _cb_parts(data: str | None, count: int) -> list[str] | None:
    """Split callback data into exactly `count` parts; None for anything malformed."""
    if not data:
        return None
    parts = data.split(":")
    return parts if len(parts) == count and all(parts) else None


def _seat(raw: str) -> int | None:
    return int(raw) if raw.isdigit() and 0 < int(raw) <= 99 else None


async def _is_admin(chat_id: int, user_id: int) -> bool:
    if user_id == app.settings.owner_id:
        return True
    try:
        member = await app.bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError:
        return False
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def _in_chat(chat_id: int, user_id: int) -> bool:
    """Whether the user is currently a member of the group; unknown counts as yes."""
    try:
        member = await app.bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError:
        return True
    return member.status not in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}


@router.message(Command("mafia", "newgame", "game"))
async def cmd_mafia(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        await message.answer(t(await _lang(message.chat.id), "mafia.group_only"))
        return
    async with app.locks(message.chat.id):
        existing = await app.store.active_in_chat(message.chat.id)
        if existing and existing.phase != Phase.FINISHED:
            if existing.phase == Phase.LOBBY:
                await app.refresh_lobby(existing)
            else:
                lang = await _lang(message.chat.id)
                await message.answer(t(lang, "mafia.busy", phase=phase_label(lang, existing.phase)))
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
    async with app.locks(message.chat.id):
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
                t(
                    await _lang(message.chat.id),
                    "join.open_dm",
                    link=f"https://t.me/{app.settings.bot_username}?start=g_{game.id}",
                ),
                link_preview_options=NO_PREVIEW,
            )


@router.message(Command("cancel", "stopmafia", "stop"))
async def cmd_cancel(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.locks(message.chat.id):
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
        await app.persist(game)
        await app.unpin_lobby(game)
        await unmute_all(app.bot, game)
        await message.answer(texts.cancelled(lang))


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not _is_group(message):
        lang = await _lang(message.chat.id)
        game = await app.store.by_user_lobby_or_live(message.from_user.id) if message.from_user else None
        if not game:
            await message.answer(t(lang, "status.none"))
            return
        await message.answer(
            t(lang, "status.phase", phase=phase_label(lang, game.phase), n=len(game.alive_players()))
        )
        return
    lang = await _lang(message.chat.id)
    game = await app.store.active_in_chat(message.chat.id)
    if not game:
        await message.answer(t(lang, "status.none"))
        return
    if game.phase == Phase.LOBBY:
        await app.refresh_lobby(game)
        return
    await message.answer(
        t(
            lang,
            "status.live",
            phase=phase_label(lang, game.phase),
            round=game.round,
            n=len(game.alive_players()),
        )
    )


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
        await _answer_with_photo(query.message, role_card(key), texts.role_card(key, lang))


@router.message(Command("leave"))
async def cmd_leave(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.locks(message.chat.id):
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
    async with app.locks(message.chat.id):
        game = await app.store.active_in_chat(message.chat.id)
        if not game:
            await message.answer(t(await _lang(message.chat.id), "extend.no_lobby"))
            return
        lang = await _lang(message.chat.id)
        if message.from_user.id not in {game.host_id, app.settings.owner_id}:
            await message.answer(t(lang, "next.host_only"))
            return
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
    await _answer_with_photo(message, media("menu_top"), texts.top_text(rows, await _lang(message.chat.id)))


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    if not message.from_user:
        return
    acc = await app.store.get_account(message.from_user.id)
    await _answer_with_photo(
        message,
        media("menu_profile"),
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
    await _answer_with_photo(
        message,
        media("menu_shop"),
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
    if _is_group(message) and message.from_user and not await _is_admin(message.chat.id, message.from_user.id):
        await message.answer(t(lang, "lang.admin_only"))
        return
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
    await _answer_with_photo(
        message,
        media("menu_help"),
        t(lang, "btn.shortcuts") if rich_ok else texts.help_text(lang),
        reply_markup=menu_kb(lang),
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    lang = await _lang(message.chat.id)
    await message.answer(texts.privacy_text(lang, app.settings.retention_days), link_preview_options=NO_PREVIEW)


@router.message(Command("terms"))
async def cmd_terms(message: Message) -> None:
    lang = await _lang(message.chat.id)
    await message.answer(texts.terms_text(lang), link_preview_options=NO_PREVIEW)


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message, command: CommandObject) -> None:
    """Telegram requires bots that sell for Stars to answer /paysupport; requests go to the owner."""
    lang = await _lang(message.chat.id)
    request = (command.args or "").strip()
    if not request or not message.from_user:
        await message.answer(t(lang, "paysupport.help"))
        return
    user = message.from_user
    who = f"@{user.username}" if user.username else user.first_name
    await app.alerts.send(
        f"paysupport:{user.id}:{message.message_id}",
        f"💬 /paysupport\nKimdan: {who} (id {user.id}, chat {message.chat.id})\n\n{request[:3000]}",
    )
    await message.answer(t(lang, "paysupport.sent"))


@router.message(Command("deletemydata"))
async def cmd_deletemydata(message: Message) -> None:
    lang = await _lang(message.chat.id)
    if message.chat.type != ChatType.PRIVATE:
        await message.answer(t(lang, "dm.only"))
        return
    await message.answer(t(lang, "delete.ask"), reply_markup=delete_kb(lang))


@router.callback_query(F.data.startswith("del:"))
async def cb_delete(query: CallbackQuery) -> None:
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user or not query.message:
        await query.answer()
        return
    lang = await _lang(query.from_user.id)
    if parts[1] != "yes":
        await query.answer()
        await query.message.edit_text(t(lang, "delete.cancelled"))
        return
    if await app.store.by_user_lobby_or_live(query.from_user.id):
        await query.answer(t(lang, "delete.busy"), show_alert=True)
        return
    result = await app.store.delete_user(query.from_user.id)
    log.info("user data deleted user=%s %s", query.from_user.id, result)
    await query.answer()
    await query.message.edit_text(t(lang, "delete.done"))


@router.message(Command("startgame"))
async def cmd_startgame(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.locks(message.chat.id):
        game = await app.store.active_in_chat(message.chat.id)
        lang = await _lang(message.chat.id)
        if not game:
            await message.answer(t(lang, "extend.no_lobby"))
            return
        if message.from_user.id not in {game.host_id, app.settings.owner_id}:
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
    found = await app.store.by_user_lobby_or_live(message.from_user.id)
    if not found:
        await message.answer(t(lang, "no_game"))
        return
    async with app.game_lock(found.id):
        game = await app.store.load(found.id)
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
    found = (
        await app.store.active_in_chat(message.chat.id)
        if _is_group(message)
        else await app.store.by_user_lobby_or_live(message.from_user.id)
    )
    if not found:
        await message.answer(t(lang, "no_game"))
        return
    async with app.game_lock(found.id):
        game = await app.store.load(found.id)
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
        await _answer_with_photo(
            message,
            media("menu_start"),
            texts.host_menu_text(lang),
            reply_markup=host_kb(app.settings.bot_username, lang),
        )
        return
    game_id = payload[2:]
    async with app.game_lock(game_id):
        game = await app.store.load(game_id)
        if not game:
            await message.answer(t(lang, "start.not_found"))
            return
        if game.phase == Phase.LOBBY and not game.by_user(message.from_user.id):
            if not await _in_chat(game.chat_id, message.from_user.id):
                await message.answer(t(lang, "start.not_member"))
                return
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
    parts = _cb_parts(query.data, 2)
    if not parts:
        await query.answer()
        return
    game_id = parts[1]
    async with app.game_lock(game_id):
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
    parts = _cb_parts(query.data, 2)
    if not parts:
        await query.answer()
        return
    game_id = parts[1]
    async with app.game_lock(game_id):
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
    parts = _cb_parts(query.data, 3)
    seat = _seat(parts[2]) if parts else None
    if not parts or seat is None:
        await query.answer()
        return
    prefix, game_id, seat_s = parts
    lang = await _lang(query.from_user.id)
    async with app.game_lock(game_id):
        game = await app.store.load(game_id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        kind = "shoot" if prefix == "ns" else ""
        ok, reason = set_night_action(game, query.from_user.id, seat, kind=kind)
        if not ok:
            await query.answer(texts.action_reason(reason, lang), show_alert=True)
            return
        await app.persist(game)
        target = game.by_seat(seat)
        await query.answer(texts.picked(target.html_label() if target else seat_s, lang))


@router.callback_query(F.data.startswith("v:"))
async def cb_vote(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = _cb_parts(query.data, 3)
    seat = _seat(parts[2]) if parts else None
    if not parts or seat is None:
        await query.answer()
        return
    _, game_id, seat_s = parts
    async with app.game_lock(game_id):
        game = await app.store.load(game_id)
        lang = await _lang(query.from_user.id)
        if not game:
            await query.answer(t(lang, "cb.no_game"), show_alert=True)
            return
        ok, reason = set_vote(game, query.from_user.id, seat)
        if not ok:
            await query.answer(texts.action_reason(reason, lang), show_alert=True)
            return
        await app.persist(game)
        target = game.by_seat(seat)
        await app.refresh_vote(game)
        await query.answer(texts.voted(target.html_label() if target else seat_s, lang), show_alert=False)


@router.callback_query(F.data.startswith("vx:"))
async def cb_vote_clear(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = _cb_parts(query.data, 2)
    if not parts:
        await query.answer()
        return
    game_id = parts[1]
    async with app.game_lock(game_id):
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


@router.callback_query(F.data.startswith("me:"))
async def cb_my_role(query: CallbackQuery) -> None:
    """Role reminder in the group, seen only by the presser (ephemeral message, Bot API 10.2)."""
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user or not query.message:
        await query.answer()
        return
    lang = await _lang(query.from_user.id)
    game = await app.store.load(parts[1])
    player = game.by_user(query.from_user.id) if game else None
    if not game or not player or not player.role:
        await query.answer(t(lang, "role.not_playing"), show_alert=True)
        return
    try:
        await app.bot.send_message(
            query.message.chat.id,
            texts.role_dm(game, query.from_user.id, lang),
            ephemeral_message_parameters=EphemeralMessageParameters(
                receiver_user_id=query.from_user.id, callback_query_id=query.id
            ),
            link_preview_options=NO_PREVIEW,
        )
        await query.answer()
    except TelegramAPIError:
        # Older clients or a rejected ephemeral: a private alert carries the role title instead.
        from tezmafia.i18n import role_title

        await query.answer(f"🔒 {role_title(lang, player.role)}", show_alert=True)


@router.my_chat_member()
async def on_my_member(update: ChatMemberUpdated) -> None:
    """Greets a group when the bot is added; cancels its table when the bot is removed."""
    if update.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    old, new = update.old_chat_member.status, update.new_chat_member.status
    gone = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
    lang = await _lang(update.chat.id)
    if new in gone:
        async with app.locks(update.chat.id):
            game = await app.store.active_in_chat(update.chat.id)
            if game:
                app.cancel_timer(game.id)
                cancel(game)
                await app.persist(game)
        log.info("bot removed from chat=%s", update.chat.id)
        return
    if old in gone:
        text = t(lang, "group.welcome")
        if new != ChatMemberStatus.ADMINISTRATOR:
            text += "\n\n" + t(lang, "group.need_admin")
        try:
            await app.bot.send_message(update.chat.id, text, link_preview_options=NO_PREVIEW)
        except TelegramAPIError:
            log.info("welcome not sent chat=%s", update.chat.id, exc_info=True)


@router.callback_query(F.data.startswith("ly:"))
async def cb_lynch(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = _cb_parts(query.data, 3)
    if not parts or parts[2] not in {"0", "1"}:
        await query.answer()
        return
    _prefix, game_id, bit = parts
    async with app.game_lock(game_id):
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
    parts = _cb_parts(query.data, 2)
    if not parts or not query.message or not query.from_user:
        await query.answer()
        return
    lang = parts[1]
    chat = query.message.chat
    if chat.type in {ChatType.GROUP, ChatType.SUPERGROUP} and not await _is_admin(chat.id, query.from_user.id):
        await query.answer(t(await _lang(chat.id), "lang.admin_only"), show_alert=True)
        return
    saved = await app.store.set_lang(chat.id, lang)
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
        await _answer_with_photo(
            query.message,
            media("menu_profile"),
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
        await _answer_with_photo(
            query.message,
            media("menu_shop"),
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
        text = texts.shop_text(acc["coins"], acc["gems"], acc["inventory"], lang)
        try:
            # The shop may be a photo with the text as its caption.
            if query.message.photo:
                await query.message.edit_caption(caption=text, reply_markup=shop_kb(lang))
            else:
                await query.message.edit_text(text, reply_markup=shop_kb(lang))
        except TelegramAPIError:
            pass


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    """Last line of defence: log, tell the user something failed, alert the owner."""
    exc = event.exception
    log.error("handler failed: %r", exc, exc_info=exc)
    update = event.update
    try:
        if update.callback_query:
            lang = await _lang(update.callback_query.from_user.id)
            await update.callback_query.answer(t(lang, "error.generic"), show_alert=True)
        elif update.message and update.message.chat.type == ChatType.PRIVATE:
            await update.message.answer(t(await _lang(update.message.chat.id), "error.generic"))
    except Exception:
        log.debug("error reply failed", exc_info=True)
    await app.alerts.send(f"handler:{type(exc).__name__}", f"⚠️ Handler xatosi: {exc!r}")
    return True


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
        BotCommand(command="privacy", description=cmd(lang, "privacy")),
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
        BotCommand(command="paysupport", description=cmd(lang, "paysupport")),
        BotCommand(command="terms", description=cmd(lang, "terms")),
        BotCommand(command="privacy", description=cmd(lang, "privacy")),
        BotCommand(command="deletemydata", description=cmd(lang, "deletemydata")),
    ]
    return default, group, private


async def _sync_bot_commands(bot: Bot) -> None:
    keys = (
        "mafia", "game", "join", "leave", "extend", "next", "status", "status_dm",
        "roles", "profile", "shop", "buy", "top", "settings", "stop", "help", "start",
        "privacy", "terms", "paysupport", "deletemydata",
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


async def _sync_bot_profile(bot: Bot) -> None:
    """Per-language bot description; re-applied only when the catalog texts change."""
    profile = {lang: (t(lang, "profile.short"), t(lang, "profile.desc")) for lang in LANGS}
    digest = hashlib.sha1(json.dumps(profile, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    marker = Path("data") / f".profile_{digest}"
    if marker.exists():
        return
    previous = list(Path("data").glob(".profile_*"))
    try:
        if not previous:
            # setMyName is flood-limited for hours; the name never changes, so set it once.
            await bot.set_my_name("TezMafia")
        for lang, tg in [("uz", None), *TG_LANG.items()]:
            short, desc = profile[lang]
            kwargs: dict = {"language_code": tg} if tg else {}
            await bot.set_my_short_description(short, **kwargs)
            await bot.set_my_description(desc, **kwargs)
        Path("data").mkdir(exist_ok=True)
        for old in previous:
            old.unlink(missing_ok=True)
        marker.write_text(digest + "\n", encoding="utf-8")
    except TelegramRetryAfter as exc:
        log.warning("profile texts flood retry_after=%s", getattr(exc, "retry_after", "?"))
    except Exception:
        log.warning("profile texts skipped (flood or reject)", exc_info=True)


async def setup_bot_profile(bot: Bot) -> None:
    await _sync_bot_profile(bot)
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
    await _sync_profile_photo(bot)


async def _sync_profile_photo(bot: Bot) -> None:
    """Upload the avatar only when the file changed; repeated uploads clutter the bot's photo history."""
    path = ASSETS / media("avatar")
    if not path.is_file():
        return
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    marker = Path("data") / f".avatar_{digest}"
    if marker.exists():
        return
    try:
        await bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=FSInputFile(path)))
    except Exception:
        log.warning("profile photo rejected", exc_info=True)
        return
    Path("data").mkdir(exist_ok=True)
    for old in Path("data").glob(".avatar_*"):
        old.unlink(missing_ok=True)
    marker.write_text(digest + "\n", encoding="utf-8")


async def run() -> None:
    global app
    settings = Settings()
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.log_file:
        from logging.handlers import RotatingFileHandler

        Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(settings.log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    instance = InstanceLock(Path("data") / ".instance.lock")
    if not instance.acquire():
        # Exit code 75 tells the autostart wrappers not to restart: the other copy is the live one.
        log.error("another TezMafia instance already polls with this data directory")
        raise SystemExit(ALREADY_RUNNING)
    store = Store(settings.database_url)
    await store.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(RetryAfterMiddleware())
    app = App(settings, store, bot)
    dp = Dispatcher()
    dp.update.outer_middleware(ActivityMiddleware(store))
    dp.include_router(router)
    try:
        await setup_bot_profile(bot)
    except Exception:
        log.exception("setup_bot_profile failed; continuing to poll")
    await app.recover()
    await assert_polling_contract(bot)
    background = [asyncio.create_task(app.watchdog()), asyncio.create_task(app.daily_report_loop())]
    await app.alerts.send("startup", f"✅ TezMafia ishga tushdi ({_build_label()})")
    log.info(
        "DECISION-01 runtime=single-node store=sqlite polling=on lock=per-chat bot=@%s",
        settings.bot_username,
    )
    log.info("polling as @%s", settings.bot_username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in background:
            task.cancel()
        instance.release()
