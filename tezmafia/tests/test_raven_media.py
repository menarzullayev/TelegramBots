"""How the bot attaches Raven artwork: role cards in DMs, caption overflow, menu headers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from tezmafia import bot as botmod
from tezmafia.bot import App, _answer_with_photo
from tezmafia.brand import CAPTION_LIMIT, media, role_card
from tezmafia.db import Store

from tests.test_bot_e2e import FakeBot, _ready_game, _settings


def _photo_path(call: tuple) -> str:
    return str(call[1][1].path).replace("\\", "/")


@pytest.fixture
async def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    application = App(_settings(), store, FakeBot())  # type: ignore[arg-type]
    botmod.app = application
    return application


@pytest.mark.asyncio
async def test_role_dm_carries_the_role_card(app: App) -> None:
    g = _ready_game()
    await app.start_game(g)
    dm_photos = [c for c in app.bot.calls if c[0] == "send_photo" and c[1][0] > 0]
    assert len(dm_photos) == len(g.players)
    for p in g.players:
        call = next(c for c in dm_photos if c[1][0] == p.user_id)
        assert _photo_path(call).endswith(role_card(p.role))
        assert call[2]["protect_content"] is True
        assert call[2]["caption"]


@pytest.mark.asyncio
async def test_dm_photo_falls_back_to_text_when_photo_breaks(app: App) -> None:
    async def broken(*a, **k):
        raise TelegramBadRequest(method=MagicMock(), message="IMAGE_PROCESS_FAILED")

    app.bot.send_photo = broken  # type: ignore[method-assign]
    assert await app.dm_photo(101, role_card("don"), "hello") is True
    assert app.bot.calls[-1][0] == "send_message"


@pytest.mark.asyncio
async def test_dm_photo_reports_closed_dm(app: App) -> None:
    async def closed(*a, **k):
        raise TelegramForbiddenError(method=MagicMock(), message="blocked")

    app.bot.send_photo = closed  # type: ignore[method-assign]
    app.bot.send_message = closed  # type: ignore[method-assign]
    assert await app.dm_photo(101, role_card("don"), "hello") is False


@pytest.mark.asyncio
async def test_long_caption_is_split_into_photo_and_text(app: App) -> None:
    long = "x" * (CAPTION_LIMIT + 1)
    await app.safe_photo(-100, media("night"), long, reply_markup="KB")
    kinds = [c[0] for c in app.bot.calls]
    assert kinds == ["send_photo", "send_message"]
    assert "caption" not in app.bot.calls[0][2]
    assert app.bot.calls[1][1][1] == long
    assert app.bot.calls[1][2]["reply_markup"] == "KB"


@pytest.mark.asyncio
async def test_short_caption_stays_on_the_photo(app: App) -> None:
    await app.safe_photo(-100, media("night"), "short")
    assert [c[0] for c in app.bot.calls] == ["send_photo"]
    assert app.bot.calls[0][2]["caption"] == "short"


class _Msg:
    def __init__(self, fail_photo: bool = False) -> None:
        self.chat = SimpleNamespace(id=5)
        self.sent: list[tuple[str, tuple, dict]] = []
        self.fail_photo = fail_photo

    async def answer(self, *a, **k):
        self.sent.append(("text", a, k))

    async def answer_photo(self, *a, **k):
        if self.fail_photo:
            raise TelegramBadRequest(method=MagicMock(), message="nope")
        self.sent.append(("photo", a, k))


@pytest.mark.asyncio
async def test_menu_header_goes_on_top_of_the_text() -> None:
    m = _Msg()
    await _answer_with_photo(m, media("menu_shop"), "shop", reply_markup="KB")
    assert [s[0] for s in m.sent] == ["photo"]
    assert m.sent[0][2] == {"caption": "shop", "reply_markup": "KB"}


@pytest.mark.asyncio
async def test_menu_header_failure_still_answers() -> None:
    m = _Msg(fail_photo=True)
    await _answer_with_photo(m, media("menu_shop"), "shop", reply_markup="KB")
    assert [s[0] for s in m.sent] == ["text"]
    assert m.sent[0][1] == ("shop",)


@pytest.mark.asyncio
async def test_unknown_role_card_answers_without_photo() -> None:
    m = _Msg()
    await _answer_with_photo(m, role_card("nope"), "?")
    assert [s[0] for s in m.sent] == ["text"]


@pytest.mark.asyncio
async def test_shop_purchase_edits_photo_caption(app: App) -> None:
    edits: list[str] = []
    msg = SimpleNamespace(
        photo=[object()],
        chat=SimpleNamespace(id=5),
        edit_caption=lambda **k: _record(edits, "caption"),
        edit_text=lambda *a, **k: _record(edits, "text"),
    )
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=7, first_name="A"), data="buy:shield", message=msg, answer=_noop
    )
    await botmod.cb_buy(query)  # type: ignore[arg-type]
    assert edits == ["caption"]
    msg.photo = None
    await botmod.cb_buy(query)  # type: ignore[arg-type]
    assert edits == ["caption", "text"]


async def _noop(*a, **k) -> None:
    return None


async def _record(log: list[str], kind: str) -> None:
    log.append(kind)
