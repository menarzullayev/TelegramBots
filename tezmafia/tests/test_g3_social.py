"""G3: result cards and sharing, inline invite, clans, weekly tournament."""

from __future__ import annotations

import io
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User
from PIL import Image

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.cards import result_card
from tezmafia.db import Store
from tezmafia.engine import start
from tezmafia.i18n import t
from tezmafia.social import CLAN_COST, TOUR_GEMS, clean_clan_name, points, week_key


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    yield application
    for task in application.timers.values():
        task.cancel()
    await store.engine.dispose()


def _msg(app: App, uid: int, text: str, sent: list[str]) -> FakeMsg:
    msg = FakeMsg(User(id=uid, is_bot=False, first_name=f"U{uid}"), Chat(id=uid, type=ChatType.PRIVATE), text, app.bot)
    msg.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
    return msg


# --- rules -----------------------------------------------------------------------------------


def test_clan_names() -> None:
    assert clean_clan_name("  Qora   Qarg'a ") is None  # apostrophe is not a letter
    assert clean_clan_name("  Qora   Qarg ") == "Qora Qarg"
    assert clean_clan_name("Ворон") == "Ворон"
    for bad in ("ab", "x" * 21, "_abc", "abc_", "", "a!b"):
        assert clean_clan_name(bad) is None


def test_week_key_and_points() -> None:
    monday = time.mktime((2026, 10, 12, 12, 0, 0, 0, 0, -1))
    sunday = time.mktime((2026, 10, 18, 23, 0, 0, 0, 0, -1))
    assert week_key(monday) == week_key(sunday) == "2026-W42"
    assert week_key(monday - 86400) == "2026-W41"
    assert points(True) > points(False) > 0


def test_result_card_is_a_jpeg_and_survives_long_names() -> None:
    data = result_card("Абдужаббор " * 8, "mafia", "Mafiya", True, "G'alaba — shahar endi Mafiyaniki", "Daraja 3 · 12")
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG" and img.size == (1280, 720)
    assert result_card("X", "no_such_role", "?", False, "", "")[:2] == b"\xff\xd8"  # no portrait still renders


# --- clans -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clan_create_costs_coins_and_names_are_unique(app: App) -> None:
    assert await app.store.create_clan(1, "A", "Ravens", CLAN_COST) == "money"
    assert await app.store.clan_of(1) is None  # failed payment leaves nothing behind
    await app.store.credit_wallet(1, "A", coins=CLAN_COST + 5)
    assert await app.store.create_clan(1, "A", "Ravens", CLAN_COST) == "ok"
    assert (await app.store.get_account(1))["coins"] == 5
    assert await app.store.create_clan(1, "A", "Other", CLAN_COST) == "member"
    await app.store.credit_wallet(2, "B", coins=CLAN_COST)
    assert await app.store.create_clan(2, "B", "rAVENS", CLAN_COST) == "taken"  # case-insensitive
    assert (await app.store.get_account(2))["coins"] == CLAN_COST  # not charged


@pytest.mark.asyncio
async def test_clan_join_limit_and_ownership_handover(app: App) -> None:
    await app.store.credit_wallet(1, "A", coins=CLAN_COST)
    await app.store.create_clan(1, "A", "Ravens", CLAN_COST)
    assert (await app.store.join_clan(2, "ravens", 3))[0] == "ok"
    assert (await app.store.join_clan(3, "ravens", 3))[0] == "ok"
    assert (await app.store.join_clan(4, "ravens", 3))[0] == "full"
    assert (await app.store.join_clan(2, "ravens", 30))[0] == "member"
    assert (await app.store.join_clan(5, "nobody", 30))[0] == "none"
    assert await app.store.leave_clan(1)
    clan = await app.store.clan_of(2)
    assert clan and clan.owner_id == 2  # oldest member inherits
    assert await app.store.leave_clan(2) and await app.store.leave_clan(3)
    assert not await app.store.leave_clan(3)
    assert (await app.store.join_clan(6, "ravens", 30))[0] == "none"  # last one out deletes the clan


@pytest.mark.asyncio
async def test_clan_command_flow(app: App) -> None:
    sent: list[str] = []
    await app.store.credit_wallet(1, "U1", coins=CLAN_COST)
    await botmod.cmd_clan(_msg(app, 1, "", sent), SimpleNamespace(args="create !!"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "clan.error", why=t("uz", "clan.why.name"))
    await botmod.cmd_clan(_msg(app, 1, "", sent), SimpleNamespace(args="create Qora Qarga"))  # type: ignore[arg-type]
    assert "Qora Qarga" in sent[-1]
    await botmod.cmd_clan(_msg(app, 2, "", sent), SimpleNamespace(args="join qora qarga"))  # type: ignore[arg-type]
    assert sent[-1].endswith(t("uz", "clan.joined", name="Qora Qarga"))
    await botmod.cmd_clan(_msg(app, 2, "", sent), SimpleNamespace(args=None))  # type: ignore[arg-type]
    assert "2/" in sent[-1]
    await botmod.cmd_clan(_msg(app, 2, "", sent), SimpleNamespace(args="top"))  # type: ignore[arg-type]
    assert "Qora Qarga" in sent[-1]
    await botmod.cmd_clan(_msg(app, 3, "", sent), SimpleNamespace(args="leave"))  # type: ignore[arg-type]
    assert sent[-1] == t("uz", "clan.error", why=t("uz", "clan.why.no_clan"))


# --- tournament ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_week_top_orders_by_points_then_wins(app: App) -> None:
    w = "2026-W42"
    await app.store.bump_week(w, 1, "A", True, points(True))
    await app.store.bump_week(w, 2, "B", False, points(False))
    await app.store.bump_week(w, 2, "B", False, points(False))
    await app.store.bump_week(w, 2, "B", False, points(False))
    await app.store.bump_week(w, 3, "C", False, points(False))
    await app.store.bump_week("2026-W41", 9, "Old", True, 99)
    top = await app.store.week_top(w)
    assert [uid for uid, _, _ in top] == [1, 2, 3]  # A 4pts/1 win beats B 3pts, C last
    assert top[0][2] == points(True)


@pytest.mark.asyncio
async def test_tournament_pays_top_three_once(app: App) -> None:
    w = "2026-W42"
    for uid in (1, 2, 3, 4):
        await app.store.credit_wallet(uid, f"P{uid}", coins=0)
        for _ in range(5 - uid):
            await app.store.bump_week(w, uid, f"P{uid}", True, points(True))
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    app.alerts.send = AsyncMock()  # type: ignore[method-assign]
    assert await app.award_tournament(w) == [1, 2, 3]
    assert await app.award_tournament(w) == []  # second run pays nothing
    for uid, gems in zip((1, 2, 3), TOUR_GEMS, strict=True):
        acc = await app.store.get_account(uid)
        assert acc["gems"] == gems and acc["badge"] == "🏆"
    assert (await app.store.get_account(4))["gems"] == 0
    assert app.dm.await_count == 3


@pytest.mark.asyncio
async def test_trophy_can_be_worn_only_by_its_owner(app: App) -> None:
    await app.store.credit_wallet(1, "A", gems=50)
    await app.store.credit_wallet(2, "B", gems=50)
    assert await app.store.buy_badge(2, "B", "trophy") == "no_item"  # cannot be bought
    await app.store.grant_badge(1, "trophy", "🏆")
    assert await app.store.buy_badge(1, "A", "star") == "bought"
    assert await app.store.buy_badge(1, "A", "trophy") == "owned"
    acc = await app.store.get_account(1)
    assert acc["badge"] == "🏆" and acc["gems"] < 50
    assert (await app.store.get_account(2))["gems"] == 50


@pytest.mark.asyncio
async def test_tournament_command_lists_this_week(app: App) -> None:
    sent: list[str] = []
    await botmod.cmd_tournament(_msg(app, 1, "", sent))  # type: ignore[arg-type]
    assert t("uz", "top.empty") in sent[-1]
    await app.store.bump_week(week_key(), 1, "Zed", True, points(True))
    await botmod.cmd_tournament(_msg(app, 1, "", sent))  # type: ignore[arg-type]
    assert "Zed" in sent[-1] and week_key() in sent[-1]


# --- game end: cards and weekly points -------------------------------------------------------


@pytest.mark.asyncio
async def test_game_end_sends_cards_and_feeds_the_week(app: App) -> None:
    g = _ready_game()
    start(g)
    g.winner = "town"
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]

    async def send_photo(chat_id, photo, **k):
        app.bot.calls.append(("send_photo", (chat_id, photo), k))
        return SimpleNamespace(message_id=1, photo=[SimpleNamespace(file_id=f"small{chat_id}"),
                                                    SimpleNamespace(file_id=f"big{chat_id}")])

    app.bot.send_photo = send_photo  # type: ignore[method-assign]
    await app.record_stats(g)
    photos = [c for c in app.bot.calls if c[0] == "send_photo"]
    assert {c[1][0] for c in photos} == {p.user_id for p in g.players}
    first = photos[0]
    assert first[2]["reply_markup"].inline_keyboard[0][0].switch_inline_query == "card"
    card = await app.store.last_card(g.players[0].user_id)
    assert card and card.file_id == f"big{g.players[0].user_id}"
    top = await app.store.week_top(week_key(), limit=50)
    assert {uid for uid, _, _ in top} == {p.user_id for p in g.players}


@pytest.mark.asyncio
async def test_card_failure_does_not_break_game_end(app: App, monkeypatch) -> None:
    g = _ready_game()
    start(g)
    g.winner = "mafia"
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]

    def boom(*a, **k):
        raise OSError("font missing")

    monkeypatch.setattr("tezmafia.cards.result_card", boom)
    await app.record_stats(g)  # must not raise
    assert await app.store.last_card(g.players[0].user_id) is None
    assert (await app.store.get_account(g.players[0].user_id))["games"] == 1


# --- inline mode -----------------------------------------------------------------------------


class _Query:
    def __init__(self, uid: int, text: str) -> None:
        self.from_user = User(id=uid, is_bot=False, first_name="Q")
        self.query = text
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_inline_offers_invite_and_card(app: App) -> None:
    q = _Query(7, "")
    await botmod.on_inline(q)  # type: ignore[arg-type]
    results = q.answer.await_args.args[0]
    assert [r.id for r in results] == ["invite"]
    assert q.answer.await_args.kwargs == {"cache_time": 0, "is_personal": True}

    await app.store.save_card(7, "FILE", "G'alaba <b>")
    q = _Query(7, "card")
    await botmod.on_inline(q)  # type: ignore[arg-type]
    results = q.answer.await_args.args[0]
    assert [r.id for r in results] == ["card", "invite"]
    assert results[0].photo_file_id == "FILE" and "&lt;b&gt;" in results[0].caption  # caption is escaped

    q = _Query(7, "hello")
    await botmod.on_inline(q)  # type: ignore[arg-type]
    assert [r.id for r in q.answer.await_args.args[0]] == ["invite", "card"]


@pytest.mark.asyncio
async def test_delete_user_removes_cards_and_weekly_rows(app: App) -> None:
    await app.store.credit_wallet(7, "A", coins=1)
    await app.store.save_card(7, "F", "c")
    await app.store.bump_week("2026-W42", 7, "A", True, 4)
    await app.store.delete_user(7)
    assert await app.store.last_card(7) is None
    assert await app.store.week_top("2026-W42") == []


def test_every_locale_has_the_g3_keys() -> None:
    from pathlib import Path

    keys = ("card.win", "btn.share", "inline.invite_title", "clan.help", "tour.won", "cmd.clan", "cmd.tournament")
    for path in (Path(botmod.__file__).parent / "locales").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert all(k in data for k in keys), path.name


@pytest.mark.asyncio
async def test_trophy_shows_in_shop_only_for_owners(app: App) -> None:
    from tezmafia.keyboards import gems_kb
    from tezmafia.webapp.server import build_state

    def keys(kb):
        return [row[0].callback_data for row in kb.inline_keyboard]

    assert "gb:trophy" not in keys(gems_kb([], ""))
    assert "gb:trophy" in keys(gems_kb(["trophy"], "🏆"))
    await app.store.credit_wallet(1, "A", coins=1)
    user = {"id": 1, "first_name": "A"}
    assert "trophy" not in [b["key"] for b in (await build_state(app, user))["badges"]]
    await app.store.grant_badge(1, "trophy", "🏆")
    badges = {b["key"]: b for b in (await build_state(app, user))["badges"]}
    assert badges["trophy"]["owned"] and badges["trophy"]["worn"]
