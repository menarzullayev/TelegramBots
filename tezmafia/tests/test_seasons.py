"""F5c: monthly and per-group rankings, game history, last words."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import cancel, start
from tezmafia.i18n import t


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    yield application
    await store.engine.dispose()


@pytest.mark.asyncio
async def test_season_ladders_are_global_and_per_group(app: App) -> None:
    await app.store.bump_season("2026-10", -1, 7, "A", True)
    await app.store.bump_season("2026-10", -1, 8, "B", False)
    await app.store.bump_season("2026-10", -2, 8, "B", True)
    await app.store.bump_season("2026-10", -2, 8, "B", True)
    assert await app.store.season_top("2026-10") == [("B", 3, 2), ("A", 1, 1)]
    assert await app.store.season_top("2026-10", -1) == [("A", 1, 1), ("B", 1, 0)]
    assert await app.store.season_top("2026-10", -2) == [("B", 2, 2)]
    assert await app.store.season_top("2026-09") == []


@pytest.mark.asyncio
async def test_game_end_feeds_the_season(app: App) -> None:
    g = _ready_game()
    start(g)
    g.winner = "town"
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    await app.record_stats(g)
    season = time.strftime("%Y-%m")
    assert len(await app.store.season_top(season)) == len(g.players)
    assert len(await app.store.season_top(season, g.chat_id)) == len(g.players)
    await app.store.delete_user(g.players[0].user_id)
    assert len(await app.store.season_top(season)) == len(g.players) - 1


def test_top_names_are_escaped() -> None:
    text = texts.top_text([("<b>evil</b>", 1, 1)], "uz", "<T>")
    assert "<b>evil</b>" not in text and "&lt;b&gt;evil" in text and "&lt;T&gt;" in text


def _top_query(view: str, chat_type: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=f"top:{view}",
        message=SimpleNamespace(chat=Chat(id=-5, type=chat_type), photo=None, edit_text=AsyncMock(), edit_caption=AsyncMock()),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_top_views_switch_in_place(app: App) -> None:
    await app.store.bump_season(time.strftime("%Y-%m"), -5, 7, "A", True)
    q = _top_query("group", ChatType.SUPERGROUP)
    await botmod.cb_top(q)  # type: ignore[arg-type]
    assert t("uz", "top.group") in q.message.edit_text.await_args.args[0]
    q = _top_query("group", ChatType.PRIVATE)  # no group ladder in a private chat
    await botmod.cb_top(q)  # type: ignore[arg-type]
    assert t("uz", "top.group") not in q.message.edit_text.await_args.args[0]
    bad = _top_query("weekly", ChatType.SUPERGROUP)
    await botmod.cb_top(bad)  # type: ignore[arg-type]
    bad.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_lists_recent_games(app: App) -> None:
    won = _ready_game()
    start(won)
    won.winner = "mafia"
    won.phase = "finished"
    await app.persist(won)
    dropped = _ready_game()
    cancel(dropped)
    await app.persist(dropped)
    games = await app.store.recent_games(-100)
    text = texts.history_text(games)
    assert t("uz", "go.short.mafia") in text and t("uz", "history.cancelled") in text
    assert texts.history_text([]) .endswith(t("uz", "history.empty"))


def _dm(user_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id), text=text, answer=AsyncMock())


@pytest.mark.asyncio
async def test_last_words_reach_the_group_once(app: App) -> None:
    g = _ready_game()
    app.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    await app.invite_last_words(g, [2])
    assert app.dm.await_args.args[0] == 101
    app.bot.send_message = AsyncMock()  # type: ignore[method-assign]
    msg = _dm(101, "I was <the> doctor")
    await botmod.on_last_words(msg)  # type: ignore[arg-type]
    posted = app.bot.send_message.await_args.args
    assert posted[0] == -100 and "&lt;the&gt;" in posted[1]
    msg.answer.assert_awaited_once()
    again = _dm(101, "one more")
    await botmod.on_last_words(again)  # type: ignore[arg-type]
    assert app.bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_late_or_uninvited_words_are_ignored(app: App) -> None:
    app.bot.send_message = AsyncMock()  # type: ignore[method-assign]
    app.pending_words[101] = (-100, "P1", time.time() - 1)
    await botmod.on_last_words(_dm(101, "too late"))  # type: ignore[arg-type]
    await botmod.on_last_words(_dm(555, "who am I"))  # type: ignore[arg-type]
    app.bot.send_message.assert_not_awaited()
