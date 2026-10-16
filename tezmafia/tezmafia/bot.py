from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from html import escape
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
    BufferedInputFile,
    CallbackQuery,
    ChatAdministratorRights,
    ChatMemberUpdated,
    EphemeralMessageParameters,
    ErrorEvent,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputProfilePhotoStatic,
    InputRichMessage,
    InputTextMessageContent,
    LabeledPrice,
    LinkPreviewOptions,
    MenuButtonWebApp,
    Message,
    PreCheckoutQuery,
    ReactionTypeEmoji,
    WebAppInfo,
)

from tezmafia import texts
from tezmafia.brand import ASSETS, caption_fits, media, role_card, win_media
from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.emoji import FX
from tezmafia.engine import (
    Game,
    Phase,
    add_bot,
    begin_lynch,
    begin_night,
    begin_voting,
    bot_lynch_votes,
    bot_night_moves,
    bot_votes,
    can_start,
    cancel,
    end_if_stalemate,
    extend_lobby,
    humans,
    is_bot,
    join,
    kick,
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
    config_kb,
    config_roles_kb,
    delete_kb,
    gems_kb,
    host_kb,
    invite_inline_kb,
    invite_kb,
    lang_kb,
    link_kb,
    lobby_kb,
    lynch_kb,
    menu_kb,
    my_role_kb,
    night_kb,
    pass_kb,
    premium_kb,
    rematch_kb,
    remind_kb,
    roles_kb,
    share_kb,
    shop_kb,
    skins_kb,
    top_kb,
    vote_kb,
)
from tezmafia.roles import NIGHT_ROLES, ROLE_FACTION, SPECIALS, Role
from tezmafia.services.analytics import ActivityMiddleware
from tezmafia.services.mute import apply_phase_mutes, unmute_all
from tezmafia.services.runtime import Alerter, ChatLocks, InstanceLock, RetryAfterMiddleware
from tezmafia.shop import (
    BADGES,
    ROLE_TICKET_COST,
    SPECIAL_BADGES,
    STAR_PACKS,
    VIP_PERIOD,
    VIP_STARS,
    resolve_item,
    resolve_role,
)

log = logging.getLogger("tezmafia")
router = Router(name="tezmafia")

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
RECOVER_GRACE = 30.0
# Mode -> timer overrides on top of the group's day/night choice.
MODES: dict[str, dict[str, int]] = {
    "classic": {},
    "chaos": {},
    "secret": {},
    "fast": {"night": 25, "day": 45, "vote": 25, "lynch": 15},
}
DAY_CHOICES = (60, 90, 120)
WORDS_SECONDS = 90  # how long an eliminated player may send last words
NIGHT_CHOICES = (30, 45, 60)
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
        # user_id -> (group chat, player label, expiry) for players invited to send last words
        self.pending_words: dict[int, tuple[int, str, float]] = {}
        self.alerts = Alerter(bot, settings.owner_id)
        self._pending_edits: dict[tuple[str, str], asyncio.Task[Any]] = {}
        # Result cards are rendered in threads; a burst of finished games must not take every core.
        self.card_slots = asyncio.Semaphore(4)

    async def chat_cfg(self, chat_id: int) -> dict[str, Any]:
        """The group's /config view: stored choices over the bot-wide defaults."""
        raw = await self.store.chat_settings(chat_id)
        s = self.settings
        return {
            "mode": raw.get("mode") if raw.get("mode") in MODES else "classic",
            "reveal": bool(raw.get("reveal", s.reveal_on_death)),
            "mute": bool(raw.get("mute", s.mute_night)),
            "day": int(raw.get("day", s.discussion_seconds)),
            "night": int(raw.get("night", s.night_action_seconds)),
            "anon": bool(raw.get("anon", False)),
            "off": [r for r in raw.get("off", []) if r in SPECIALS],
        }

    async def game_cfg(self, chat_id: int) -> dict[str, Any]:
        """new_game() arguments: the group's settings frozen into the game at /game time."""
        c = await self.chat_cfg(chat_id)
        s = self.settings
        timers = {"night": c["night"], "day": c["day"], "vote": s.voting_seconds, "lynch": s.lynch_seconds}
        timers.update(MODES[c["mode"]])
        timers["mute"] = int(c["mute"])  # stored with the timers so a running game keeps its rule
        return {
            **self.cfg(),
            "reveal_on_death": c["reveal"] and c["mode"] != "secret",
            "mode": c["mode"],
            "timers": timers,
            "disabled_roles": c["off"],
            "anon_vote": c["anon"],
        }

    def timer(self, game: Game, key: str) -> int:
        s = self.settings
        defaults = {"night": s.night_action_seconds, "day": s.discussion_seconds, "vote": s.voting_seconds, "lynch": s.lynch_seconds}
        return int(game.timers.get(key) or defaults[key])

    def mute_on(self, game: Game) -> bool:
        return bool(game.timers.get("mute", int(self.settings.mute_night)))

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
        if is_bot(user_id):
            return True
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
        if is_bot(user_id):
            return True
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

    def _defer_edit(self, kind: str, game_id: str, edit: Callable[[str], Awaitable[None]]) -> bool:
        """Merge edits that arrive within edit_debounce into one; False means edit right now."""
        delay = self.settings.edit_debounce
        if delay <= 0:
            return False
        key = (kind, game_id)
        if key in self._pending_edits:
            return True

        async def later() -> None:
            await asyncio.sleep(delay)
            self._pending_edits.pop(key, None)
            try:
                await edit(game_id)
            except Exception:
                log.warning("deferred %s edit failed game=%s", kind, game_id, exc_info=True)

        self._pending_edits[key] = asyncio.create_task(later())
        return True

    async def _edit_vote_latest(self, game_id: str) -> None:
        async with self.game_lock(game_id):  # same lock as every other writer of this game
            game = await self.store.load(game_id)
            if game and game.phase == Phase.VOTING:
                await self._edit_vote(game)

    async def _edit_lobby_latest(self, game_id: str) -> None:
        # refresh_lobby may persist (new lobby message): without the lock it could write back a stale game
        async with self.game_lock(game_id):
            game = await self.store.load(game_id)
            if game and game.phase == Phase.LOBBY and game.lobby_message_id:
                await self.refresh_lobby(game, now=True)

    async def refresh_vote(self, game: Game) -> None:
        if not game.vote_message_id:
            return
        if self._defer_edit("vote", game.id, self._edit_vote_latest):
            return
        await self._edit_vote(game)

    async def _edit_vote(self, game: Game) -> None:
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

    async def refresh_lobby(self, game: Game, now: bool = False) -> None:
        if game.lobby_message_id and not now and self._defer_edit("lobby", game.id, self._edit_lobby_latest):
            return
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
            except TelegramBadRequest as e:
                if "not modified" in str(e).lower():  # same text: the lobby is already current
                    return
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

    async def open_lobby(self, chat_id: int, user_id: int, first_name: str, username: str | None) -> Game:
        """New table with the caller seated as host; the caller holds the chat lock."""
        game = new_game(chat_id, user_id, **(await self.game_cfg(chat_id)))
        join(game, user_id, first_name, username)
        player = game.by_user(user_id)
        if player:
            player.badge = await self.store.shown_badge(user_id)
        game.deadline = time.time() + self.settings.lobby_seconds
        await self.persist(game)
        await self.refresh_lobby(game)
        self.schedule(game.id, self.settings.lobby_seconds, lambda gid=game.id: self._timed_lobby_expire(gid))
        return game

    async def invite_last_words(self, game: Game, seats: list[int]) -> None:
        for seat in seats:
            player = game.by_seat(seat)
            if not player:
                continue
            self.pending_words[player.user_id] = (game.chat_id, player.html_label(), time.time() + WORDS_SECONDS)
            lang = await self.lang(player.user_id)
            text = t(lang, "words.prompt", sec=WORDS_SECONDS) + "\n\n💀 " + t(lang, "dead.joined")
            await self.dm(player.user_id, text)

    async def send_role_dms(self, game: Game) -> bool:
        """Role card to every player; False when at least one DM is closed."""
        for p in game.players:
            effect = FX["fire"] if p.faction == "mafia" else FX["heart"]
            skin = "" if is_bot(p.user_id) else (await self.store.skins_of(p.user_id))[0]
            ok = await self.dm_photo(
                p.user_id,
                role_card(p.role or "", skin),
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
        if end_if_stalemate(game):
            await self.finish(game)
            return
        begin_night(game, time.time(), self.timer(game, "night"))
        bot_night_moves(game, random.Random())
        await self.persist(game)
        self.schedule(game.id, self.timer(game, "night"), lambda: self._timed_resolve_night(game.id))
        await apply_phase_mutes(self.bot, game, night=True, enabled=self.mute_on(game))
        group_lang = await self.lang(game.chat_id)
        await self.safe_photo(
            game.chat_id, media("night"), texts.night_group(game, group_lang), reply_markup=my_role_kb(game, group_lang)
        )
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
        game.deadline = time.time() + self.timer(game, "day")
        game.version += 1
        await self.persist(game)
        self.schedule(game.id, self.timer(game, "day"), lambda: self._timed_begin_vote(game.id))
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.mute_on(game))
        day_lang = await self.lang(game.chat_id)
        caption = (
            texts.day_group(game, game.reveal_on_death, day_lang)
            if from_night
            else texts.day_group(game, False, day_lang)
        )
        banner_name = media("dawn_death") if game.last_death_seat else media("dawn")
        await self.safe_photo(game.chat_id, banner_name, caption, reply_markup=my_role_kb(game, day_lang))

    async def enter_vote(self, game: Game) -> None:
        begin_voting(game, time.time(), self.timer(game, "vote"))
        bot_votes(game, random.Random())
        await self.persist(game)
        self.schedule(game.id, self.timer(game, "vote"), lambda: self._timed_resolve_vote(game.id))
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.mute_on(game))
        vote_lang = await self.lang(game.chat_id)
        msg = await self.safe_group(game, texts.vote_tally(game, vote_lang), reply_markup=vote_kb(game, vote_lang))
        if msg:
            game.vote_message_id = msg.message_id
            await self.persist(game)

    async def record_stats(self, game: Game) -> None:
        from tezmafia.engine import player_won
        from tezmafia.progress import Outcome, earned, level_of, xp_for
        from tezmafia.retention import QUEST_COINS, QUEST_XP, quest_increments, todays_quests
        from tezmafia.social import FAIR_AFK_PENALTY, FAIR_GAME_BONUS, reward_tier, week_key

        notes: dict[int, str] = {}
        quest_notes: dict[int, list[str]] = {}
        card_jobs: list[tuple[Any, bool, dict[str, int]]] = []
        retry = self.store.retry
        afk_seats = {ev.get("seat") for ev in game.chronicle if ev.get("cause") == "afk"}
        people = humans(game)
        tier = reward_tier(len(people), len(game.players))
        rows = [(p.user_id, p.first_name, player_won(game, p), p.alive, p.seat in afk_seats) for p in people]
        all_totals = await retry(lambda: self.store.record_game(
            game.id, game.chat_id, rows, time.strftime("%Y-%m"), week_key(), (FAIR_AFK_PENALTY, FAIR_GAME_BONUS), tier
        ))
        for p in people:
            won = player_won(game, p)
            totals = all_totals[p.user_id]
            card_jobs.append((p, won, totals))
            if tier != "full":  # with bots at the table: no quests, achievements or referral payouts (no farming)
                notes[p.user_id] = t(await self.lang(p.user_id), "bot.reward_note", humans=len(people))
                continue
            outcome = Outcome(
                role=p.role or "", faction=p.faction or "", winner=game.winner or "", won=won, alive=p.alive, **totals
            )
            day = time.strftime("%Y-%m-%d")
            uid, name, incs = p.user_id, p.first_name, quest_increments(day, outcome)
            done_quests = await retry(lambda uid=uid, incs=incs, day=day: self.store.quest_advance(day, uid, incs))
            if done_quests:
                n = len(done_quests)
                await retry(lambda uid=uid, name=name, n=n: self.store.credit_wallet(uid, name, coins=QUEST_COINS * n))
                await retry(lambda uid=uid, n=n: self.store.add_xp(uid, QUEST_XP * n))
                state = await self.store.quest_state(day, uid)
                if all(state.get(k, (0, False))[1] for k in todays_quests(day)):
                    await retry(lambda uid=uid, name=name: self.store.credit_wallet(uid, name, gems=1))
                quest_notes[uid] = done_quests
            # First full game pays the referral; take_referral pays once, so bot-table games played earlier don't lose it.
            await retry(lambda uid=uid, name=name: self.reward_referral(uid, name))
            keys = earned(outcome)
            fresh = await retry(lambda uid=uid, keys=keys: self.store.award(uid, keys))
            before, after = level_of(totals["xp"] - xp_for(won, p.alive)), level_of(totals["xp"])
            if fresh or after > before or uid in quest_notes:
                lang = await self.lang(uid)
                lines = [texts.progress_dm(fresh, after if after > before else None, lang),
                         *texts.quest_lines(quest_notes.get(uid, []), lang)]
                notes[uid] = "\n".join(line for line in lines if line)
        await self.reward_founder(game)
        for p, won, totals in card_jobs:
            # progress news rides on the card's caption: one message per player instead of two
            if not await self.send_card(game, p, won, totals, extra=notes.get(p.user_id, "")) and notes.get(p.user_id):
                await self.dm(p.user_id, notes[p.user_id])

    async def send_card(self, game: Game, player: Any, won: bool, totals: dict[str, int], extra: str = "") -> bool:
        """Shareable result card in the player's DM; its file id is kept for inline sharing."""
        from tezmafia.cards import result_card
        from tezmafia.i18n import role_title
        from tezmafia.progress import level_of

        lang = await self.lang(player.user_id)
        result = t(lang, "card.draw" if game.winner == "draw" else "card.win" if won else "card.loss")
        winner = t(lang, f"go.short.{texts.outcome_key(game)}") if game.winner else ""
        line = f"{result} — {winner}".rstrip(" —.")
        footer = t(lang, "card.footer", level=level_of(totals["xp"]), games=totals["games"])
        premium = await self.store.chat_premium(game.chat_id)
        if premium and premium[1]:
            footer = f"{premium[1]} · {footer}"
        caption = escape(line) + (f"\n\n{extra}" if extra else "")
        if len(caption) > 1024:  # Telegram's caption limit; the news then goes as its own DM
            caption, extra = escape(line), ""
        try:
            skin = (await self.store.skins_of(player.user_id))[0]
            async with self.card_slots:
                data = await asyncio.to_thread(
                    result_card, player.first_name, player.role or "citizen", role_title(lang, player.role or "citizen"),
                    won, line, f"{footer} · @{self.settings.bot_username}", skin,
                )
            msg = await self.bot.send_photo(
                player.user_id, BufferedInputFile(data, "tezmafia.jpg"), caption=caption, reply_markup=share_kb(lang),
            )
        except (TelegramAPIError, OSError):
            log.info("result card not sent user=%s", player.user_id, exc_info=True)
            return False
        photos = getattr(msg, "photo", None)
        if photos:
            await self.store.save_card(player.user_id, photos[-1].file_id, line)
        return bool(extra)

    async def tournament_loop(self) -> None:
        """Every Monday 10:00 local time: pay last week's top three."""
        while True:
            now = time.localtime()
            days = (7 - now.tm_wday) % 7
            target = time.mktime((now.tm_year, now.tm_mon, now.tm_mday + days, 10, 0, 0, 0, 0, -1))
            if target <= time.time():
                target += 7 * 86400
            await asyncio.sleep(target - time.time())
            try:
                await self.award_tournament()
            except Exception:
                log.exception("tournament awards failed")
            try:
                from tezmafia.social import week_key as wk

                await self.weekly_digest(wk(time.time() - 3 * 86400))
            except Exception:
                log.exception("weekly digest failed")

    async def award_tournament(self, week: str | None = None) -> list[int]:
        from tezmafia.social import TOUR_GEMS
        from tezmafia.social import week_key as wk

        week = week or wk(time.time() - 3 * 86400)  # Monday 10:00 minus 3 days lands in last week
        if not await self.store.claim_tournament(week):
            return []
        winners = await self.store.week_top(week, limit=len(TOUR_GEMS))
        emoji = SPECIAL_BADGES["trophy"][0]
        for place, ((uid, name, _pts), gems) in enumerate(zip(winners, TOUR_GEMS, strict=False), start=1):
            await self.store.credit_wallet(uid, name, gems=gems)
            await self.store.grant_badge(uid, "trophy", emoji)
            await self.dm(uid, "🏆 " + t(await self.lang(uid), "tour.won", place=place, gems=gems))
        if winners:
            await self.alerts.send(f"tour:{week}", f"🏆 Turnir {week}: " + ", ".join(n for _, n, _ in winners))
        return [uid for uid, _, _ in winners]

    async def reward_founder(self, game: Game) -> None:
        """The admin who added the bot is paid once when the group plays its first full game."""
        from tezmafia.social import FOUNDER_COINS, FOUNDER_GEMS, FOUNDER_MAX_GROUPS, FOUNDER_MIN_PLAYERS

        if not game.winner or len(humans(game)) < FOUNDER_MIN_PLAYERS:
            return
        uid = await self.store.claim_founder_reward(game.chat_id, FOUNDER_MAX_GROUPS)
        if uid is None:
            return
        await self.store.credit_wallet(uid, "", coins=FOUNDER_COINS, gems=FOUNDER_GEMS)
        await self.store.grant_badge(uid, "founder", SPECIAL_BADGES["founder"][0])
        await self.dm(uid, t(await self.lang(uid), "founder.reward", coins=FOUNDER_COINS, gems=FOUNDER_GEMS))

    async def weekly_digest(self, week: str, post: bool = True) -> str:
        """Monday digest: channel post (when configured) and the owner's funnel report."""
        from tezmafia.keyboards import add_group_url
        from tezmafia.social import TOUR_GEMS

        season = time.strftime("%Y-%m")
        start = time.time() - 7 * 86400
        f = await self.store.funnel(start)
        winners = await self.store.week_top(week, limit=len(TOUR_GEMS))
        clans = await self.store.clan_top(season, limit=5)
        text = texts.weekly_digest(week, f["finished"], await self.store.week_players(week), winners, clans, "uz")
        if post and self.settings.news_channel:
            try:
                await self.bot.send_photo(
                    self.settings.news_channel, FSInputFile(ASSETS / media("menu_top")), caption=text,
                    reply_markup=link_kb(t("uz", "btn.add_group"), add_group_url(self.settings.bot_username)),
                )
            except TelegramAPIError:
                log.warning("weekly channel post failed", exc_info=True)
        report = "\n".join([f"<b>{t('uz', 'funnel.title')}</b>", *texts.funnel_lines(f, "uz")])
        if post and self.settings.owner_id:
            await self.dm(self.settings.owner_id, report)
        return text + "\n\n" + report

    async def reward_referral(self, user_id: int, name: str) -> None:
        """A referred player's first finished game pays both sides once."""
        from tezmafia.retention import REF_INVITER_COINS, REF_NEW_COINS

        referrer = await self.store.take_referral(user_id)
        if not referrer:
            return
        await self.store.credit_wallet(user_id, name, coins=REF_NEW_COINS)
        await self.store.credit_wallet(referrer, "", coins=REF_INVITER_COINS)
        await self.dm(
            referrer, t(await self.lang(referrer), "invite.reward", name=escape(name), coins=REF_INVITER_COINS)
        )

    async def scheduler_loop(self, interval: float = 30.0) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await self.scheduler_pass()
            except Exception:
                log.exception("scheduler pass failed")

    async def scheduler_pass(self, now: float | None = None, lead: float = 900.0) -> None:
        """Remind subscribers ~15 minutes ahead, then open the lobby on time."""
        now = now or time.time()
        for sch in await self.store.open_schedules():
            lang = await self.lang(sch.chat_id)
            when = f'<tg-time unix="{int(sch.at)}" format="t">{time.strftime("%H:%M", time.localtime(sch.at))}</tg-time>'
            if sch.state == "pending" and now >= sch.at - lead:
                await self.store.set_schedule_state(sch.id, "notified")
                for uid in await self.store.schedule_subscribers(sch.id):
                    await self.dm(uid, t(await self.lang(uid), "sched.soon", when=when))
                try:
                    await self.bot.send_message(sch.chat_id, "⏰ " + t(lang, "sched.soon", when=when))
                except TelegramAPIError:
                    log.info("schedule notice failed chat=%s", sch.chat_id, exc_info=True)
            if now >= sch.at:
                await self.store.set_schedule_state(sch.id, "started")
                async with self.locks(sch.chat_id):
                    if not await self.store.active_in_chat(sch.chat_id):
                        await self.open_lobby(sch.chat_id, sch.created_by, sch.creator_name or "Host", None)

    async def streak_reminder_loop(self, hour: int = 19) -> None:
        while True:
            now = time.localtime()
            target = time.mktime((*now[:3], hour, 0, 0, 0, 0, -1))
            if target <= time.time():
                target += 86400
            await asyncio.sleep(target - time.time())
            try:
                yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
                for uid, streak in await self.store.streaks_at_risk(yesterday):
                    await self.dm(uid, t(await self.lang(uid), "daily.remind", streak=streak))
            except Exception:
                log.exception("streak reminders failed")

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
                self.safe_photo(game.chat_id, name, short, reply_markup=rematch_kb(game, await self.lang(game.chat_id))),
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
            await self.invite_last_words(game, list(game.night_deaths))
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
        begin_lynch(game, seat, time.time(), self.timer(game, "lynch"))
        bot_lynch_votes(game, random.Random())
        await self.persist(game)
        self.schedule(game.id, self.timer(game, "lynch"), lambda: self._timed_resolve_lynch(game.id))
        await apply_phase_mutes(self.bot, game, night=False, enabled=self.mute_on(game))
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
                texts.elim_group(game, result["tie"], game.reveal_on_death, await self.lang(game.chat_id)),
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
            if result["confirmed"] and game.last_death_seat:
                await self.invite_last_words(game, [game.last_death_seat])
            verdict = texts.elim_group(
                game, not result["confirmed"], game.reveal_on_death, await self.lang(game.chat_id)
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
        await self.store.optimize()
        await self.store.prune_activity()
        yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        month = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))
        dau = await self.store.active_users(yesterday)
        mau = await self.store.active_users(month)
        mau_dm = await self.store.active_users(month, "dm")
        paid, stars = await self.store.stars_since(time.time() - 86400)
        return (
            "📊 TezMafia, oxirgi 24 soat\n"
            f"O'yinlar: {r['games']} (bekor: {r['cancelled']}), guruhlar: {r['chats']}\n"
            f"O'yinchilar: {r['players']}, yangi: {r['new_users']}, jami: {r['users']}\n"
            f"Faol: kun {dau} · 30 kun {mau} (DM orqali {mau_dm})\n"
            f"Stars: {stars}⭐ ({paid} ta to'lov)\n"
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


async def _wear_badge(game: Game, user_id: int) -> None:
    player = game.by_user(user_id)
    if player:
        player.badge = await app.store.shown_badge(user_id)


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
        user = message.from_user
        if await app.store.is_banned(message.chat.id, user.id):
            await message.answer(t(await _lang(message.chat.id), "mod.you_banned"))
            return
        await app.open_lobby(message.chat.id, user.id, user.first_name, user.username)


@router.message(Command("join"))
async def cmd_join(message: Message) -> None:
    if not message.from_user or not _is_group(message):
        return
    async with app.locks(message.chat.id):
        game = await app.store.active_in_chat(message.chat.id)
        if not game or game.phase != Phase.LOBBY:
            await message.answer(t(await _lang(message.chat.id), "extend.no_lobby"))
            return
        if await app.store.is_banned(message.chat.id, message.from_user.id):
            await message.answer(t(await _lang(message.chat.id), "mod.you_banned"))
            return
        ok, reason = join(game, message.from_user.id, message.from_user.first_name, message.from_user.username)
        await _wear_badge(game, message.from_user.id)
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


async def _top_view(view: str, chat_id: int, lang: str) -> str:
    season = time.strftime("%Y-%m")
    if view == "all":
        return texts.top_text(await app.store.cached(("top_all",), app.store.top_stats), lang, t(lang, "btn.top_all"))
    if view == "group":
        rows = await app.store.cached(("season", season, chat_id), lambda: app.store.season_top(season, chat_id))
        return texts.top_text(rows, lang, t(lang, "top.group"))
    rows = await app.store.cached(("season", season, 0), lambda: app.store.season_top(season))
    return texts.top_text(rows, lang, t(lang, "top.season", season=season))


@router.message(Command("top"))
async def cmd_top(message: Message) -> None:
    lang = await _lang(message.chat.id)
    view = "season" if await app.store.season_top(time.strftime("%Y-%m"), limit=1) else "all"
    text = await _top_view(view, message.chat.id, lang)
    await _answer_with_photo(message, media("menu_top"), text, reply_markup=top_kb(view, _is_group(message), lang))


@router.callback_query(F.data.startswith("top:"))
async def cb_top(query: CallbackQuery) -> None:
    parts = _cb_parts(query.data, 2)
    if not parts or parts[1] not in {"season", "group", "all"} or not query.message:
        await query.answer()
        return
    chat = query.message.chat
    in_group = chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}
    view = parts[1] if in_group or parts[1] != "group" else "season"
    lang = await _lang(chat.id)
    text = await _top_view(view, chat.id, lang)
    await query.answer()
    try:
        if query.message.photo:
            await query.message.edit_caption(caption=text, reply_markup=top_kb(view, in_group, lang))
        else:
            await query.message.edit_text(text, reply_markup=top_kb(view, in_group, lang))
    except TelegramAPIError:
        pass


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    lang = await _lang(message.chat.id)
    if not _is_group(message):
        await message.answer(t(lang, "mafia.group_only"))
        return
    await message.answer(texts.history_text(await app.store.recent_games(message.chat.id), lang))


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
            vip_until=acc.get("vip_until"),
            badge=acc.get("badge", ""),
            xp=acc.get("xp", 0),
            achievements=await app.store.achievement_count(message.from_user.id),
            fair=await app.store.fair_play(message.from_user.id),
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
                    vip_until=acc.get("vip_until"),
                    badge=acc.get("badge", ""),
                    xp=acc.get("xp", 0),
                    achievements=await app.store.achievement_count(message.from_user.id),
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


@router.message(Command("config"))
async def cmd_config(message: Message) -> None:
    lang = await _lang(message.chat.id)
    if not _is_group(message):
        await message.answer(t(lang, "mafia.group_only"))
        return
    cfg = await app.chat_cfg(message.chat.id)
    await message.answer(texts.config_text(cfg, lang), reply_markup=config_kb(cfg, lang))


@router.callback_query(F.data.startswith("cfg:"))
async def cb_config(query: CallbackQuery) -> None:
    parts = (query.data or "").split(":")
    if len(parts) not in (2, 3) or not query.from_user or not query.message:
        await query.answer()
        return
    chat_id = query.message.chat.id
    lang = await _lang(chat_id)
    if not await _is_admin(chat_id, query.from_user.id):
        await query.answer(t(lang, "config.admin_only"), show_alert=True)
        return
    cfg = await app.chat_cfg(chat_id)
    key = parts[1]
    if key == "mode" and len(parts) == 3 and parts[2] in MODES:
        await app.store.set_chat_setting(chat_id, "mode", parts[2])
    elif key in ("reveal", "mute", "anon"):
        await app.store.set_chat_setting(chat_id, key, not cfg[key])
    elif key == "roles":
        await query.answer()
        try:
            await query.message.edit_text(t(lang, "config.roles_title"), reply_markup=config_roles_kb(cfg["off"], lang))
        except TelegramAPIError:
            pass
        return
    elif key == "back":
        pass
    elif key in ("day", "night"):
        from tezmafia.shop import PREMIUM_DAY_CHOICES, PREMIUM_NIGHT_CHOICES

        if await app.store.chat_premium(chat_id):
            choices = PREMIUM_DAY_CHOICES if key == "day" else PREMIUM_NIGHT_CHOICES
        else:
            choices = DAY_CHOICES if key == "day" else NIGHT_CHOICES
        nxt = choices[(choices.index(cfg[key]) + 1) % len(choices)] if cfg[key] in choices else choices[0]
        await app.store.set_chat_setting(chat_id, key, nxt)
    else:
        await query.answer()
        return
    cfg = await app.chat_cfg(chat_id)
    await query.answer(t(lang, "config.saved"))
    try:
        await query.message.edit_text(texts.config_text(cfg, lang), reply_markup=config_kb(cfg, lang))
    except TelegramAPIError:
        pass


def _app_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "app.open"), web_app=WebAppInfo(url=app.settings.webapp_url))]]
    )


async def _send_app(message: Message, lang: str) -> None:
    """web_app buttons work only in private chats; groups get a deep link that opens the bot."""
    if not app.settings.webapp_url:
        await message.answer(t(lang, "app.error"))
        return
    if _is_group(message):
        link = f"https://t.me/{app.settings.bot_username}?start=app"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "app.open"), url=link)]])
        await message.answer(t(lang, "app.hint"), reply_markup=kb)
        return
    await message.answer(t(lang, "app.hint"), reply_markup=_app_kb(lang))


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    await _send_app(message, await _lang(message.chat.id))


@router.callback_query(F.data.startswith("cfr:"))
async def cb_config_role(query: CallbackQuery) -> None:
    """Switch one special role on or off for the group's next tables."""
    parts = _cb_parts(query.data, 2)
    if not parts or parts[1] not in SPECIALS or not query.from_user or not query.message:
        await query.answer()
        return
    chat_id = query.message.chat.id
    lang = await _lang(chat_id)
    if not await _is_admin(chat_id, query.from_user.id):
        await query.answer(t(lang, "config.admin_only"), show_alert=True)
        return
    off = (await app.chat_cfg(chat_id))["off"]
    off = [r for r in off if r != parts[1]] if parts[1] in off else [*off, parts[1]]
    await app.store.set_chat_setting(chat_id, "off", off)
    await query.answer(t(lang, "config.saved"))
    try:
        await query.message.edit_reply_markup(reply_markup=config_roles_kb(off, lang))
    except TelegramAPIError:
        pass


@router.callback_query(F.data.startswith("rm:"))
async def cb_rematch(query: CallbackQuery) -> None:
    """One tap after a game: a new lobby in the same group, and the previous players get a DM invite."""
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user or not query.message:
        await query.answer()
        return
    old = await app.store.load(parts[1])
    chat_id = query.message.chat.id
    lang = await _lang(chat_id)
    if not old or old.chat_id != chat_id:
        await query.answer()
        return
    user = query.from_user
    async with app.locks(chat_id):
        existing = await app.store.active_in_chat(chat_id)
        if existing:
            await query.answer(t(lang, "mafia.busy", phase=phase_label(lang, existing.phase)), show_alert=True)
            return
        game = await app.open_lobby(chat_id, user.id, user.first_name, user.username)
    await query.answer()
    link = f"https://t.me/{app.settings.bot_username}?start=g_{game.id}"
    for p in old.players:
        if p.user_id != user.id:
            await app.dm(p.user_id, t(await app.lang(p.user_id), "rematch.invite", host=escape(user.first_name), link=link))


@router.message(Command("daily"))
async def cmd_daily(message: Message) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    today = time.strftime("%Y-%m-%d")
    yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    got = await app.store.claim_daily(message.from_user.id, message.from_user.first_name, today, yesterday)
    if got is None:
        midnight = time.mktime((*time.localtime()[:3], 0, 0, 0, 0, 0, -1)) + 86400
        when = f'<tg-time unix="{int(midnight)}" format="r">00:00</tg-time>'
        await message.answer(t(lang, "daily.already", when=when))
        return
    gem = t(lang, "daily.gem") if got["gems"] else ""
    await message.answer("🎁 " + t(lang, "daily.got", coins=got["coins"], gem=gem, streak=got["streak"]))


@router.message(Command("quests"))
async def cmd_quests(message: Message) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    day = time.strftime("%Y-%m-%d")
    await message.answer(texts.quests_text(day, await app.store.quest_state(day, message.from_user.id), lang))


@router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    if not message.from_user:
        return
    from tezmafia.retention import REF_INVITER_COINS, REF_NEW_COINS

    lang = await _lang(message.chat.id)
    link = f"https://t.me/{app.settings.bot_username}?start=ref_{message.from_user.id}"
    n = await app.store.referral_count(message.from_user.id)
    await message.answer(
        t(lang, "invite.text", you=REF_INVITER_COINS, them=REF_NEW_COINS, n=n, link=link),
        reply_markup=invite_kb(link, lang),
        link_preview_options=NO_PREVIEW,
    )


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, command: CommandObject) -> None:
    lang = await _lang(message.chat.id)
    if not message.from_user or not _is_group(message):
        await message.answer(t(lang, "mafia.group_only"))
        return
    if not await _is_admin(message.chat.id, message.from_user.id):
        await message.answer(t(lang, "config.admin_only"))
        return
    arg = (command.args or "").strip().lower()
    if arg in ("off", "stop", "cancel"):
        await app.store.cancel_schedule(message.chat.id)
        await message.answer(t(lang, "sched.off"))
        return
    at = _parse_hhmm(arg)
    if at is None:
        await message.answer(t(lang, "sched.usage"))
        return
    sid = await app.store.create_schedule(message.chat.id, at, message.from_user.id, message.from_user.first_name)
    when = f'<tg-time unix="{int(at)}" format="wDT">{time.strftime("%d.%m %H:%M", time.localtime(at))}</tg-time>'
    await message.answer("📅 " + t(lang, "sched.set", when=when), reply_markup=remind_kb(sid, lang))


def _parse_hhmm(raw: str, now: float | None = None) -> float | None:
    """Next local occurrence of HH:MM (today if still ahead, else tomorrow)."""
    parts = raw.replace(".", ":").split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    hh, mm = int(parts[0]), int(parts[1])
    if not (0 <= hh < 24 and 0 <= mm < 60):
        return None
    now = now or time.time()
    lt = time.localtime(now)
    at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
    return at if at > now + 60 else at + 86400


@router.callback_query(F.data.startswith("sub:"))
async def cb_subscribe(query: CallbackQuery) -> None:
    parts = _cb_parts(query.data, 2)
    if not parts or not parts[1].isdigit() or not query.from_user:
        await query.answer()
        return
    lang = await _lang(query.from_user.id)
    ok = await app.store.subscribe(int(parts[1]), query.from_user.id)
    await query.answer(t(lang, "sched.subscribed") if ok else t(lang, "sched.off"), show_alert=not ok)


@router.inline_query()
async def on_inline(query: InlineQuery) -> None:
    """Inline mode: the player's latest result card (query "card") and an invite card for any chat."""
    lang = await _lang(query.from_user.id)
    results: list[Any] = []
    card = await app.store.last_card(query.from_user.id)
    if card:
        results.append(
            InlineQueryResultCachedPhoto(
                id="card", photo_file_id=card.file_id, title=t(lang, "inline.card_title"), caption=escape(card.caption),
                reply_markup=invite_inline_kb(app.settings.bot_username, lang),
            )
        )
    results.append(
        InlineQueryResultArticle(
            id="invite",
            title=t(lang, "inline.invite_title"),
            description=t(lang, "inline.invite_desc"),
            input_message_content=InputTextMessageContent(message_text=t(lang, "inline.invite_text")),
            reply_markup=invite_inline_kb(app.settings.bot_username, lang),
        )
    )
    if query.query.strip().lower() != "card":
        results.reverse()  # plain mention: the invite first
    await query.answer(results, cache_time=0, is_personal=True)


@router.message(Command("clan"))
async def cmd_clan(message: Message, command: CommandObject) -> None:
    from tezmafia.social import CLAN_COST, CLAN_MAX, clean_clan_name

    if not message.from_user:
        return
    user = message.from_user
    lang = await _lang(message.chat.id)
    action, _, rest = (command.args or "").strip().partition(" ")
    action = action.lower()
    season = time.strftime("%Y-%m")

    async def fail(why: str) -> None:
        await message.answer(t(lang, "clan.error", why=t(lang, f"clan.why.{why}")))

    if action == "create":
        name = clean_clan_name(rest)
        if not name:
            await fail("name")
            return
        result = await app.store.create_clan(user.id, user.first_name, name, CLAN_COST)
        if result != "ok":
            await fail(result)
            return
        await message.answer("🛡 " + t(lang, "clan.created", name=escape(name)))
    elif action == "join":
        name = clean_clan_name(rest)
        result, clan = await app.store.join_clan(user.id, name or rest, CLAN_MAX) if name else ("none", None)
        if result != "ok" or not clan:
            await fail(result)
            return
        await message.answer("🛡 " + t(lang, "clan.joined", name=escape(clan.name)))
    elif action == "leave":
        if not await app.store.leave_clan(user.id):
            await fail("no_clan")
            return
        await message.answer(t(lang, "clan.left"))
    elif action == "top":
        rows = await app.store.cached(("clan_top", season), lambda: app.store.clan_top(season))
        lines = [f"🛡 <b>{t(lang, 'clan.top', season=season)}</b>"]
        lines += [f"{i}. {escape(n)} — {w} · 👥{m}" for i, (n, m, w) in enumerate(rows, start=1)]
        await message.answer("\n".join(lines) if rows else t(lang, "top.empty"))
    else:
        clan = await app.store.clan_of(user.id)
        text = t(lang, "clan.help", cost=CLAN_COST)
        if clan:
            members, wins = await app.store.clan_stats(clan.id, season)
            text = "🛡 " + t(lang, "clan.info", name=escape(clan.name), n=members, max=CLAN_MAX, wins=wins) + "\n\n" + text
        await message.answer(text)


@router.message(Command("tournament"))
async def cmd_tournament(message: Message) -> None:
    from tezmafia.social import TOUR_GEMS, week_key

    lang = await _lang(message.chat.id)
    week = week_key()
    rows = await app.store.cached(("week", week), lambda: app.store.week_top(week))
    lines = [f"🏆 <b>{t(lang, 'tour.title', week=week)}</b>", t(lang, "tour.rules", g1=TOUR_GEMS[0], g2=TOUR_GEMS[1], g3=TOUR_GEMS[2]), ""]
    lines += [t(lang, "tour.row", i=i, name=escape(n), points=p) for i, (_, n, p) in enumerate(rows, start=1)]
    if not rows:
        lines.append(t(lang, "top.empty"))
    await message.answer("\n".join(lines))


async def _mod_target(message: Message, command: CommandObject, game: Game | None) -> tuple[int, str] | None:
    """Target of a moderation command: the replied-to user, a seat number, or a numeric user id."""
    reply = message.reply_to_message
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user.id, reply.from_user.first_name
    arg = (command.args or "").strip()
    seat = _seat(arg)
    if game and seat:
        p = game.by_seat(seat)
        return (p.user_id, p.first_name) if p else None
    if arg.isdigit() and len(arg) > 3:
        known = (await app.store.get_account(int(arg)))["name"]  # show a name, not the raw id, when we know it
        return int(arg), known or arg
    return None


async def _remove_from_game(game: Game, user_id: int) -> bool:
    """Kick from the lobby or the running game; finishes the game if that decides it. Caller holds the lock."""
    done, winner = kick(game, user_id)
    if not done:
        return False
    if game.phase == Phase.LOBBY:
        await app.persist(game)
        await app.refresh_lobby(game)
    elif winner:
        await app.finish(game)
    else:
        await app.persist(game)
    return True


async def _mod_prelude(message: Message, command: CommandObject) -> tuple[str, Game | None, tuple[int, str]] | None:
    if not message.from_user or not _is_group(message):
        return None
    lang = await _lang(message.chat.id)
    if not await _is_admin(message.chat.id, message.from_user.id):
        await message.answer(t(lang, "mod.admin_only"))
        return None
    game = await app.store.active_in_chat(message.chat.id)
    target = await _mod_target(message, command, game)
    if not target:
        await message.answer(t(lang, "mod.usage"))
        return None
    return lang, game, target


@router.message(Command("kick"))
async def cmd_kick(message: Message, command: CommandObject) -> None:
    async with app.locks(message.chat.id):
        ready = await _mod_prelude(message, command)
        if not ready:
            return
        lang, game, (uid, name) = ready
        if not game or not await _remove_from_game(game, uid):
            await message.answer(t(lang, "mod.not_found"))
            return
        await message.answer(t(lang, "mod.kicked", name=escape(name)))


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject) -> None:
    async with app.locks(message.chat.id):
        ready = await _mod_prelude(message, command)
        if not ready:
            return
        lang, game, (uid, name) = ready
        await app.store.ban(message.chat.id, uid, message.from_user.id if message.from_user else 0)
        if game and game.phase != Phase.FINISHED:
            await _remove_from_game(game, uid)
        await message.answer(t(lang, "mod.banned", name=escape(name)))


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject) -> None:
    ready = await _mod_prelude(message, command)
    if not ready:
        return
    lang, _game, (uid, name) = ready
    await app.store.unban(message.chat.id, uid)
    await message.answer(t(lang, "mod.unbanned", name=escape(name)))


@router.message(Command("groupstats"))
async def cmd_groupstats(message: Message) -> None:
    lang = await _lang(message.chat.id)
    if not _is_group(message):
        await message.answer(t(lang, "mafia.group_only"))
        return
    season = time.strftime("%Y-%m")
    stats = await app.store.cached(("group", message.chat.id, season), lambda: app.store.group_stats(message.chat.id, season))
    text = texts.group_stats_text(stats, season, lang)
    if await app.store.chat_premium(message.chat.id):
        lines = ["", t(lang, "gs.months")]
        for back in range(3):
            month = _month_back(back)
            top = await app.store.season_top(month, chat_id=message.chat.id, limit=1)
            m = await app.store.cached(("group", message.chat.id, month), lambda m=month: app.store.group_stats(message.chat.id, m))
            if top:
                name, _games, wins = top[0]
                lines.append(t(lang, "gs.month_row", month=month, players=m["players"], name=escape(name), wins=wins))
        text += "\n".join(lines) if len(lines) > 2 else ""
    await message.answer(text)


def _month_back(back: int) -> str:
    """YYYY-MM `back` months before this one."""
    y, m = time.localtime().tm_year, time.localtime().tm_mon - back
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


async def _pass_view(user_id: int, lang: str) -> tuple[str, Any]:
    from tezmafia.season_pass import PASS_START, PASS_TIERS, PASS_XP_PER_TIER, active, claimable, tier_of

    season = time.strftime("%Y-%m")
    if not active(season):
        return t(lang, "pass.soon", season=PASS_START), None
    xp, premium, taken = await app.store.pass_state(season, user_id)
    tier = tier_of(xp)
    left = 0 if tier >= PASS_TIERS else (tier + 1) * PASS_XP_PER_TIER - xp
    lines = [f"<b>{t(lang, 'pass.title', season=season)}</b>",
             t(lang, "pass.progress", tier=tier, tiers=PASS_TIERS, xp=xp, left=left), "", t(lang, "pass.tracks")]
    if premium:
        lines.append(t(lang, "pass.premium_on"))
    return "\n".join(lines), pass_kb(len(claimable(xp, premium, taken)), premium, lang)


@router.message(Command("pass"))
async def cmd_pass(message: Message) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    text, kb = await _pass_view(message.from_user.id, lang)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("ps:"))
async def cb_pass(query: CallbackQuery) -> None:
    from tezmafia.season_pass import active

    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user:
        await query.answer()
        return
    user, lang, season = query.from_user, await _lang(query.from_user.id), time.strftime("%Y-%m")
    if not active(season):
        await query.answer()
        return
    if parts[1] == "buy":
        title, desc, stars, _coins = _product("pass", lang)  # type: ignore[misc]
        try:
            await app.bot.send_invoice(
                user.id, title=title, description=desc, payload=f"pass:{user.id}:{season}", currency="XTR",
                prices=[LabeledPrice(label=title, amount=stars)],
            )
        except TelegramForbiddenError:
            await query.answer(t(lang, "stars.open_dm"), show_alert=True)
            return
        await query.answer()
        return
    if parts[1] == "claim":
        got = await app.store.claim_pass(season, user.id, user.first_name)
        if not got["ids"]:
            await query.answer(t(lang, "pass.nothing"), show_alert=True)
            return
        extra = ""
        if got["skin"]:
            extra += t(lang, "pass.extra_skin", name=t(lang, f"skin.{got['skin']}"))
        if got["badge"]:
            extra += t(lang, "pass.extra_badge")
        await query.answer(t(lang, "pass.claimed", coins=got["coins"], gems=got["gems"], extra=extra), show_alert=True)
        if query.message:
            text, kb = await _pass_view(user.id, lang)
            try:
                await query.message.edit_text(text, reply_markup=kb)
            except TelegramAPIError:
                pass
        return
    await query.answer()


@router.message(Command("premium"))
async def cmd_premium(message: Message) -> None:
    from tezmafia.shop import GROUP_PREMIUM_STARS

    lang = await _lang(message.chat.id)
    if not _is_group(message):
        await message.answer(t(lang, "mafia.group_only"))
        return
    active = await app.store.chat_premium(message.chat.id)
    status = t(lang, "premium.active", date=texts.date_tag(active[0])) if active else ""
    text = f"<b>{t(lang, 'premium.title')}</b>\n{status}\n{t(lang, 'premium.pitch', stars=GROUP_PREMIUM_STARS)}"
    await message.answer(text.replace("\n\n", "\n"), reply_markup=premium_kb(message.chat.id, lang))


@router.callback_query(F.data.startswith("gp:"))
async def cb_premium(query: CallbackQuery) -> None:
    """Any member: the subscription link goes to their private chat (payload gp:<payer>:<group>)."""
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user or not parts[1].lstrip("-").isdigit():
        await query.answer()
        return
    user_id, chat_id = query.from_user.id, int(parts[1])
    lang = await _lang(user_id)
    title, desc, stars, _coins = _product("gp", lang)  # type: ignore[misc]
    group = query.message.chat.title if query.message and query.message.chat.title else str(chat_id)
    try:
        link = await app.bot.create_invoice_link(
            title=title, description=desc, payload=f"gp:{user_id}:{chat_id}", currency="XTR",
            prices=[LabeledPrice(label=title, amount=stars)], subscription_period=VIP_PERIOD,
        )
        await app.bot.send_message(user_id, t(lang, "premium.link_dm", title=escape(group)), reply_markup=link_kb(title, link))
    except TelegramForbiddenError:
        await query.answer(t(lang, "stars.open_dm"), show_alert=True)
        return
    await query.answer(t(lang, "premium.link_sent"), show_alert=True)


async def _activate_premium(pay: Any, user: Any, lang: str, message: Message) -> None:
    parts = pay.invoice_payload.split(":")
    chat_id = int(parts[2]) if len(parts) > 2 and parts[2].lstrip("-").isdigit() else 0
    if not chat_id:
        log.error("premium payment without a group: %s", pay.invoice_payload)
        return
    until = float(pay.subscription_expiration_date or (time.time() + VIP_PERIOD))
    title = ""
    try:
        title = (await app.bot.get_chat(chat_id)).title or ""
    except TelegramAPIError:
        log.info("premium: group title unavailable chat=%s", chat_id)
    await app.store.set_chat_premium(chat_id, user.id, until, title)
    note = t(await _lang(chat_id), "premium.paid", name=escape(user.first_name), date=texts.date_tag(until))
    await message.answer(note)
    try:
        await app.bot.send_message(chat_id, note)
    except TelegramAPIError:
        log.info("premium: group announcement failed chat=%s", chat_id)


async def _seat_bots(game: Game, user_id: int, count: int, lang: str) -> str | None:
    """Host (or owner) fills seats with bots; returns a refusal text or None."""
    if user_id not in {game.host_id, app.settings.owner_id}:
        return t(lang, "next.host_only")
    for _ in range(max(1, min(count, 22))):
        ok, reason = add_bot(game, t(lang, "bot.name"))
        if not ok:
            if reason == "full":
                break
            return t(lang, "extend.no_lobby")
    await app.persist(game)
    await app.refresh_lobby(game)
    return None


@router.message(Command("addbot"))
async def cmd_addbot(message: Message, command: CommandObject) -> None:
    if not message.from_user or not _is_group(message):
        return
    lang = await _lang(message.chat.id)
    arg = (command.args or "").strip()
    async with app.locks(message.chat.id):
        game = await app.store.active_in_chat(message.chat.id)
        if not game or game.phase != Phase.LOBBY:
            await message.answer(t(lang, "extend.no_lobby"))
            return
        refusal = await _seat_bots(game, message.from_user.id, int(arg) if arg.isdigit() else 1, lang)
    if refusal:
        await message.answer(refusal)


@router.callback_query(F.data.startswith("ab:"))
async def cb_addbot(query: CallbackQuery) -> None:
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user:
        await query.answer()
        return
    lang = await _lang(query.from_user.id)
    async with app.game_lock(parts[1]):
        game = await app.store.load(parts[1])
        if not game or game.phase != Phase.LOBBY:
            await query.answer(t(lang, "extend.no_lobby"), show_alert=True)
            return
        refusal = await _seat_bots(game, query.from_user.id, 1, lang)
    await query.answer(refusal or "🤖", show_alert=bool(refusal))


def _skins_text(gems: int, lang: str) -> str:
    from tezmafia.shop import SKIN_COST

    return f"<b>{t(lang, 'skins.title')}</b>\n{t(lang, 'skins.body', cost=SKIN_COST, gems=gems)}"


@router.message(Command("skins"))
async def cmd_skins(message: Message) -> None:
    if not message.from_user:
        return
    lang = await _lang(message.chat.id)
    worn, owned = await app.store.skins_of(message.from_user.id)
    gems = (await app.store.get_account(message.from_user.id))["gems"]
    await _answer_with_photo(
        message, "raven/skins/preview.jpg", _skins_text(gems, lang), reply_markup=skins_kb(owned, worn, lang)
    )


@router.callback_query(F.data.startswith("sk:"))
async def cb_skin(query: CallbackQuery) -> None:
    from tezmafia.shop import SKIN_COST, SKINS

    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user or not query.message:
        await query.answer()
        return
    user = query.from_user
    lang = await _lang(user.id)
    if parts[1] == "off":
        await app.store.take_off_skin(user.id)
        note = t(lang, "skins.removed")
    elif parts[1] in SKINS:
        result = await app.store.buy_skin(user.id, user.first_name, parts[1], SKIN_COST)
        note = t(lang, {"bought": "skins.bought", "owned": "skins.worn", "no_gems": "gems.no_gems"}[result])
    else:
        await query.answer()
        return
    await query.answer(note, show_alert=True)
    worn, owned = await app.store.skins_of(user.id)
    gems = (await app.store.get_account(user.id))["gems"]
    try:
        await query.message.edit_caption(caption=_skins_text(gems, lang), reply_markup=skins_kb(owned, worn, lang))
    except TelegramAPIError:
        await query.message.answer(_skins_text(gems, lang), reply_markup=skins_kb(owned, worn, lang))


@router.message(Command("weekly"))
async def cmd_weekly(message: Message, command: CommandObject) -> None:
    """Owner only: /weekly shows the digest and the funnel; /weekly post also posts it to the channel."""
    from tezmafia.social import week_key

    if not message.from_user or message.from_user.id != app.settings.owner_id:
        return
    text = await app.weekly_digest(week_key(), post=(command.args or "").strip() == "post")
    await message.answer(text)


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
    if payload.startswith("ref_") and payload[4:].isdigit():
        from tezmafia.retention import REF_NEW_COINS

        if await app.store.add_referral(message.from_user.id, int(payload[4:])):
            await message.answer(t(lang, "invite.welcome", coins=REF_NEW_COINS))
        payload = ""
    if payload == "app":
        await _send_app(message, lang)
        return
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
            if await app.store.is_banned(game.chat_id, message.from_user.id):
                await message.answer(t(lang, "mod.you_banned"))
                return
            join(game, message.from_user.id, message.from_user.first_name, message.from_user.username)
            await _wear_badge(game, message.from_user.id)
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
        adder = getattr(update, "from_user", None)
        if adder and not adder.is_bot:
            await app.store.record_founder(update.chat.id, adder.id)
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
                vip_until=acc.get("vip_until"),
                badge=acc.get("badge", ""),
                xp=acc.get("xp", 0),
                achievements=await app.store.achievement_count(query.from_user.id),
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
    if action == "gems":
        acc = await app.store.get_account(query.from_user.id)
        owned = await app.store.owned_badges(query.from_user.id)
        await query.message.answer(texts.gems_text(acc["gems"], lang), reply_markup=gems_kb(owned, acc["badge"], lang))
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


def _product(key: str, lang: str) -> tuple[str, str, int, int] | None:
    """(title, description, stars, coins) for a Stars product key, or None."""
    if key == "vip":
        return "TezMafia VIP", t(lang, "stars.inv_desc_vip"), VIP_STARS, 0
    if key == "pass":
        from tezmafia.season_pass import PASS_STARS

        season = time.strftime("%Y-%m")
        return f"Qorashahar pass {season}", t(lang, "pass.inv_desc", season=season), PASS_STARS, 0
    if key == "gp":
        from tezmafia.shop import GROUP_PREMIUM_STARS

        title = "TezMafia Premium"
        return title, t(lang, "premium.inv_desc", title=title), GROUP_PREMIUM_STARS, 0
    if key in STAR_PACKS:
        stars, coins = STAR_PACKS[key]
        return t(lang, "stars.inv_title_pack", coins=coins), t(lang, "stars.inv_desc_pack", coins=coins), stars, coins
    return None


@router.callback_query(F.data.startswith("st:"))
async def cb_stars(query: CallbackQuery) -> None:
    """Send a Stars invoice (or the VIP subscription link) to the buyer's private chat."""
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user:
        await query.answer()
        return
    user_id = query.from_user.id
    lang = await _lang(user_id)
    product = _product(parts[1], lang)
    if not product:
        await query.answer()
        return
    title, desc, stars, _coins = product
    payload = f"{parts[1]}:{user_id}"
    try:
        if parts[1] == "vip":
            link = await app.bot.create_invoice_link(
                title=title, description=desc, payload=payload, currency="XTR",
                prices=[LabeledPrice(label=title, amount=stars)], subscription_period=VIP_PERIOD,
            )
            await app.bot.send_message(user_id, t(lang, "stars.vip_link"), reply_markup=link_kb(title, link))
        else:
            await app.bot.send_invoice(
                user_id, title=title, description=desc, payload=payload, currency="XTR",
                prices=[LabeledPrice(label=title, amount=stars)],
            )
    except TelegramForbiddenError:
        await query.answer(t(lang, "stars.open_dm"), show_alert=True)
        return
    private = query.message is not None and query.message.chat.type == ChatType.PRIVATE
    await query.answer(None if private else t(lang, "stars.sent_dm"), show_alert=not private)


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    """Telegram waits up to 10 s for this answer; reject anything that does not match our catalogue."""
    lang = await _lang(query.from_user.id)
    key, _, rest = query.invoice_payload.partition(":")
    owner = rest.split(":")[0]  # "gp:<user>:<chat>" carries the group after the payer
    product = _product(key, lang)
    ok = (
        product is not None
        and owner == str(query.from_user.id)
        and query.currency == "XTR"
        and query.total_amount == product[2]
    )
    await query.answer(ok=ok, error_message=None if ok else t(lang, "stars.bad_payload"))


@router.message(F.successful_payment)
async def on_paid(message: Message) -> None:
    pay = message.successful_payment
    if not pay or not message.from_user:
        return
    user = message.from_user
    lang = await _lang(user.id)
    key = pay.invoice_payload.partition(":")[0]
    product = _product(key, lang)
    coins = product[3] if product else 0
    fresh = await app.store.record_payment(
        pay.telegram_payment_charge_id, user.id, user.first_name, key, pay.total_amount, coins
    )
    if not fresh:
        return  # replayed update: already credited
    who = f"@{user.username}" if user.username else user.first_name
    await app.alerts.send(
        f"paid:{pay.telegram_payment_charge_id}", f"💰 +{pay.total_amount}⭐ {key} — {who} (id {user.id})"
    )
    if key == "vip":
        until = float(pay.subscription_expiration_date or (time.time() + VIP_PERIOD))
        await app.store.set_vip(user.id, user.first_name, until)
        await message.answer(t(lang, "stars.paid_vip", date=texts.date_tag(until)))
        return
    if key == "gp":
        await _activate_premium(pay, user, lang, message)
        return
    if key == "pass":
        parts = pay.invoice_payload.split(":")
        season = parts[2] if len(parts) > 2 else time.strftime("%Y-%m")
        await app.store.set_pass_premium(season, user.id)
        await message.answer(t(lang, "pass.paid", season=season))
        return
    acc = await app.store.get_account(user.id)
    await message.answer(t(lang, "stars.paid_coins", coins=coins, balance=acc["coins"]))


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject) -> None:
    """Owner only: /refund <telegram_payment_charge_id> returns the Stars and takes the goods back."""
    if not message.from_user or message.from_user.id != app.settings.owner_id:
        return
    charge = (command.args or "").strip()
    pay = await app.store.refund(charge) if charge else None
    if not pay:
        await message.answer("Topilmadi yoki allaqachon qaytarilgan.", parse_mode=None)
        return
    try:
        await app.bot.refund_star_payment(pay.user_id, charge)
        if pay.product in ("vip", "gp"):
            await app.bot.edit_user_star_subscription(pay.user_id, charge, is_canceled=True)
    except TelegramAPIError as exc:
        await message.answer(f"Bazada belgilandi, lekin Telegram rad etdi: {exc}", parse_mode=None)
        return
    await message.answer(f"Qaytarildi: {pay.stars}⭐ → {pay.user_id} ({pay.product})", parse_mode=None)


@router.callback_query(F.data.startswith("gb:"))
async def cb_badge(query: CallbackQuery) -> None:
    parts = _cb_parts(query.data, 2)
    if not parts or not query.from_user or not query.message:
        await query.answer()
        return
    user = query.from_user
    lang = await _lang(user.id)
    if parts[1] == "off":
        await app.store.take_off_badge(user.id)
        note = t(lang, "gems.removed")
    elif parts[1] in BADGES or parts[1] in SPECIAL_BADGES:
        result = await app.store.buy_badge(user.id, user.first_name, parts[1])
        if result == "no_item":
            await query.answer()
            return
        note = t(lang, {"bought": "gems.bought", "owned": "gems.equipped", "no_gems": "gems.no_gems"}[result])
    else:
        await query.answer()
        return
    await query.answer(note, show_alert=True)
    acc = await app.store.get_account(user.id)
    owned = await app.store.owned_badges(user.id)
    try:
        await query.message.edit_text(texts.gems_text(acc["gems"], lang), reply_markup=gems_kb(owned, acc["badge"], lang))
    except TelegramAPIError:
        pass


@router.message(F.chat.type == ChatType.PRIVATE, F.text, ~F.text.startswith("/"))
async def on_last_words(message: Message) -> None:
    """The first plain message an eliminated player sends within the window goes to the group."""
    if not message.from_user or not message.text:
        return
    pending = app.pending_words.pop(message.from_user.id, None)
    if not pending or time.time() > pending[2]:
        await _relay_dead(message)
        return
    chat_id, label, expires = pending
    group_lang = await _lang(chat_id)
    text = escape(message.text.strip()[:300])
    try:
        await app.bot.send_message(chat_id, "📜 " + t(group_lang, "words.post", name=label, text=text))
    except TelegramAPIError:
        log.info("last words not delivered chat=%s", chat_id, exc_info=True)
        return
    await message.answer(t(await _lang(message.from_user.id), "words.sent"))


async def _relay_dead(message: Message) -> None:
    """Room of the dead: a dead player's DM goes to the other dead players of the same live game."""
    if not message.from_user or not message.text:
        return
    game = await app.store.by_user_lobby_or_live(message.from_user.id)
    if not game or game.phase in (Phase.LOBBY, Phase.FINISHED):
        return
    me = game.by_user(message.from_user.id)
    if not me or me.alive:
        return
    text = f"💀 {me.html_label()}: {escape(message.text.strip()[:300])}"
    for p in game.players:
        if not p.alive and p.user_id != me.user_id:
            await app.dm(p.user_id, text)


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
        BotCommand(command="config", description=cmd(lang, "config")),
        BotCommand(command="history", description=cmd(lang, "history")),
        BotCommand(command="schedule", description=cmd(lang, "schedule")),
        BotCommand(command="addbot", description=cmd(lang, "addbot")),
        BotCommand(command="premium", description=cmd(lang, "premium")),
        BotCommand(command="groupstats", description=cmd(lang, "groupstats")),
        BotCommand(command="kick", description=cmd(lang, "kick")),
        BotCommand(command="ban", description=cmd(lang, "ban")),
        BotCommand(command="unban", description=cmd(lang, "unban")),
        BotCommand(command="help", description=cmd(lang, "help")),
    ]
    private = [
        BotCommand(command="start", description=cmd(lang, "start")),
        BotCommand(command="help", description=cmd(lang, "help")),
        BotCommand(command="profile", description=cmd(lang, "profile")),
        BotCommand(command="skins", description=cmd(lang, "skins")),
        BotCommand(command="pass", description=cmd(lang, "pass")),
        BotCommand(command="shop", description=cmd(lang, "shop")),
        BotCommand(command="buy", description=cmd(lang, "buy")),
        BotCommand(command="roles", description=cmd(lang, "roles")),
        BotCommand(command="status", description=cmd(lang, "status_dm")),
        BotCommand(command="app", description=cmd(lang, "app")),
        BotCommand(command="daily", description=cmd(lang, "daily")),
        BotCommand(command="quests", description=cmd(lang, "quests")),
        BotCommand(command="invite", description=cmd(lang, "invite")),
        BotCommand(command="clan", description=cmd(lang, "clan")),
        BotCommand(command="tournament", description=cmd(lang, "tournament")),
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
        "privacy", "terms", "paysupport", "deletemydata", "config", "history", "app",
        "daily", "quests", "invite", "schedule", "clan", "tournament", "groupstats", "kick", "ban", "unban", "addbot", "skins", "premium", "pass",
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
    handlers: list[logging.Handler] = []
    if settings.log_file:
        from logging.handlers import RotatingFileHandler

        Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(settings.log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"))
        # stderr (kept by the supervisor without rotation) only gets warnings and crashes.
        stream = logging.StreamHandler()
        stream.setLevel(logging.WARNING)
        handlers.append(stream)
    else:
        handlers.append(logging.StreamHandler())
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
    store.cache_ttl = 60.0  # rankings may lag up to a minute; at 1M users they cost 50 ms - 1 s uncached
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
    background = [
        asyncio.create_task(app.watchdog()),
        asyncio.create_task(app.daily_report_loop()),
        asyncio.create_task(app.scheduler_loop()),
        asyncio.create_task(app.streak_reminder_loop()),
        asyncio.create_task(app.tournament_loop()),
    ]
    web_runner = None
    if settings.webapp_port:
        from tezmafia.webapp.server import start_server

        try:
            web_runner = await start_server(app, settings.webapp_port)
        except OSError:
            log.exception("mini app server failed to start on port %s", settings.webapp_port)
    if settings.webapp_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="TezMafia", web_app=WebAppInfo(url=settings.webapp_url))
            )
        except TelegramAPIError:
            log.warning("menu button not set", exc_info=True)
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
        if web_runner:
            await web_runner.cleanup()
        instance.release()
