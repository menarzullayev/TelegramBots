"""H1: founder reward, funnel, weekly digest and the owner's Mini App admin tab."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus, ChatType

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import Phase, start
from tezmafia.i18n import t
from tezmafia.social import FOUNDER_COINS, FOUNDER_GEMS, FOUNDER_MAX_GROUPS

OWNER = 1


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    application.dm = AsyncMock(return_value=True)  # type: ignore[method-assign]
    yield application
    for task in application.timers.values():
        task.cancel()
    await store.engine.dispose()


def _finished(chat_id: int, n: int = 5, winner: str | None = "town"):
    g = _ready_game(n)
    g.chat_id = chat_id
    start(g)
    g.winner, g.phase = winner, Phase.FINISHED
    return g


def _joined(chat_id: int, user_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type=ChatType.SUPERGROUP),
        old_chat_member=SimpleNamespace(status=ChatMemberStatus.LEFT),
        new_chat_member=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR),
        from_user=SimpleNamespace(id=user_id, is_bot=False),
    )


@pytest.mark.asyncio
async def test_founder_paid_once_after_first_full_game(app: App) -> None:
    await botmod.on_my_member(_joined(-10, 77))  # type: ignore[arg-type]
    await botmod.on_my_member(_joined(-10, 88))  # a re-add by someone else keeps the first founder
    small = _finished(-10)
    small.players = small.players[:4]
    await app.record_stats(small)  # too small: no reward yet
    assert (await app.store.get_account(77))["coins"] == 0
    await app.record_stats(_finished(-10))
    acc = await app.store.get_account(77)
    assert (acc["coins"], acc["gems"], acc["badge"]) == (FOUNDER_COINS, FOUNDER_GEMS, "🎖")
    app.dm.assert_any_await(77, t("uz", "founder.reward", coins=FOUNDER_COINS, gems=FOUNDER_GEMS))
    await app.record_stats(_finished(-10))  # second game pays nothing
    assert (await app.store.get_account(77))["coins"] == FOUNDER_COINS
    assert (await app.store.get_account(88))["coins"] == 0


@pytest.mark.asyncio
async def test_founder_cap_and_cancelled_games(app: App) -> None:
    for c in range(FOUNDER_MAX_GROUPS + 1):
        await app.store.record_founder(-100 - c, 55)
    await app.record_stats(_finished(-100, winner=None))  # cancelled: nothing
    assert await app.store.claim_founder_reward(-100, FOUNDER_MAX_GROUPS) == 55  # still claimable
    for c in range(1, FOUNDER_MAX_GROUPS):
        assert await app.store.claim_founder_reward(-100 - c, FOUNDER_MAX_GROUPS) == 55
    assert await app.store.claim_founder_reward(-100 - FOUNDER_MAX_GROUPS, FOUNDER_MAX_GROUPS) is None  # over the cap
    assert await app.store.claim_founder_reward(-999, FOUNDER_MAX_GROUPS) is None  # unknown group


@pytest.mark.asyncio
async def test_funnel_counts_each_step(app: App) -> None:
    await app.store.record_founder(-1, 5)
    await app.store.record_founder(-2, 5)
    lobby = _ready_game(5)  # never started
    lobby.chat_id = -1
    await app.persist(lobby)
    for chat, winner in ((-1, "town"), (-1, "mafia"), (-2, "town"), (-2, None)):
        g = _finished(chat, winner=winner)
        if winner is None:
            g.night_no = 0  # cancelled before the first night
        await app.persist(g)
    f = await app.store.funnel(time.time() - 60)
    assert f == {"added": 2, "lobbies": 5, "started": 3, "finished": 3, "repeat": 1}
    assert await app.store.funnel(time.time() + 60) == {"added": 0, "lobbies": 0, "started": 0, "finished": 0, "repeat": 0}


@pytest.mark.asyncio
async def test_weekly_digest_posts_to_channel_and_reports_to_owner(app: App) -> None:
    from tezmafia.social import week_key

    app.settings.news_channel = "-1001"
    app.settings.owner_id = OWNER
    await app.record_stats(_finished(-5))
    text = await app.weekly_digest(week_key())
    posts = [c for c in app.bot.calls if c[0] == "send_photo" and c[1][0] == "-1001"]
    assert len(posts) == 1 and t("uz", "news.title", week=week_key()) in posts[0][2]["caption"]
    leaders = await app.store.week_top(week_key(), limit=3)
    assert leaders and all(name in posts[0][2]["caption"] for _, name, _ in leaders)  # this week's leaders are named
    app.dm.assert_any_await(OWNER, text.split("\n\n")[-1])
    app.bot.calls.clear()
    app.dm.reset_mock()
    await app.weekly_digest(week_key(), post=False)  # preview: no channel post, no duplicate owner DM
    assert not [c for c in app.bot.calls if c[0] == "send_photo" and c[1][0] == "-1001"]
    app.dm.assert_not_awaited()


@pytest.mark.asyncio
async def test_weekly_command_is_owner_only(app: App) -> None:
    from aiogram.types import Chat, User

    app.settings.owner_id = OWNER
    sent: list[str] = []
    for uid in (2, OWNER):
        msg = FakeMsg(User(id=uid, is_bot=False, first_name="U"), Chat(id=uid, type=ChatType.PRIVATE), "/weekly", app.bot)
        msg.answer = AsyncMock(side_effect=lambda text, **k: sent.append(text))  # type: ignore[method-assign]
        await botmod.cmd_weekly(msg, SimpleNamespace(args=None))  # type: ignore[arg-type]
    assert len(sent) == 1 and t("uz", "funnel.title") in sent[0]


@pytest.mark.asyncio
async def test_admin_tab_only_for_the_owner(app: App) -> None:
    from tezmafia.webapp.server import build_state

    app.settings.owner_id = OWNER
    assert (await build_state(app, {"id": 2, "first_name": "X"}))["admin"] is None
    admin = (await build_state(app, {"id": OWNER, "first_name": "O"}))["admin"]
    assert admin and admin["lines"][0].startswith(t("uz", "funnel.added"))
    assert (await build_state(SimpleNamespace(store=app.store), {"id": OWNER, "first_name": "O"}))["admin"] is None
