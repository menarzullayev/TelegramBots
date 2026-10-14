"""F2: privacy/terms texts, payment support relay and user data deletion."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User

from tests.test_bot_e2e import FakeBot, FakeMsg, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import cancel, join, new_game
from tezmafia.i18n import LANGS, t

URLS = json.loads((Path(texts.__file__).with_name("legal_urls.json")).read_text(encoding="utf-8"))


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


def _capture(msg: FakeMsg) -> list[tuple[str, dict]]:
    sent: list[tuple[str, dict]] = []

    async def answer(text, **k):
        sent.append((text, k))

    msg.answer = answer  # type: ignore[method-assign]
    return sent


@pytest.mark.parametrize("lang", LANGS)
def test_every_language_links_a_full_text(lang: str) -> None:
    privacy = texts.privacy_text(lang, 90)
    terms = texts.terms_text(lang)
    assert "https://telegra.ph/" in privacy and "https://telegra.ph/" in terms
    assert "/deletemydata" in privacy and "/paysupport" in terms
    assert "90" in privacy


def test_full_texts_exist_in_three_languages() -> None:
    for kind in ("privacy", "terms"):
        assert set(URLS[kind]) == {"uz", "ru", "en"}
    assert texts._legal_url("privacy", "kz") == URLS["privacy"]["ru"]
    assert texts._legal_url("privacy", "tr") == URLS["privacy"]["en"]


@pytest.mark.asyncio
async def test_paysupport_without_text_explains_how(app: App) -> None:
    user = User(id=5, is_bot=False, first_name="A")
    msg = FakeMsg(user, Chat(id=5, type=ChatType.PRIVATE), "/paysupport", app.bot)
    sent = _capture(msg)
    await botmod.cmd_paysupport(msg, SimpleNamespace(args=None))  # type: ignore[arg-type]
    assert sent[0][0] == t("uz", "paysupport.help")


@pytest.mark.asyncio
async def test_paysupport_request_reaches_owner(app: App) -> None:
    app.alerts.send = AsyncMock(return_value=True)  # type: ignore[method-assign]
    user = User(id=5, is_bot=False, first_name="A", username="alice")
    msg = FakeMsg(user, Chat(id=5, type=ChatType.PRIVATE), "/paysupport paid 100", app.bot)
    sent = _capture(msg)
    await botmod.cmd_paysupport(msg, SimpleNamespace(args="paid 100, no coins"))  # type: ignore[arg-type]
    text = app.alerts.send.await_args.args[1]
    assert "@alice" in text and "id 5" in text and "paid 100, no coins" in text
    assert sent[0][0] == t("uz", "paysupport.sent")


@pytest.mark.asyncio
async def test_deletemydata_is_private_only(app: App) -> None:
    user = User(id=5, is_bot=False, first_name="A")
    msg = FakeMsg(user, Chat(id=-1, type=ChatType.GROUP, title="G"), "/deletemydata", app.bot)
    sent = _capture(msg)
    await botmod.cmd_deletemydata(msg)  # type: ignore[arg-type]
    assert sent[0][0] == t("uz", "dm.only")


def _query(data: str, user_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_delete_erases_wallet_language_and_names(app: App) -> None:
    await app.store.credit_wallet(101, "P1", coins=50)
    await app.store.set_lang(101, "ru")
    done = _ready_game()
    cancel(done)
    await app.persist(done)

    q = _query("del:yes", 101)
    await botmod.cb_delete(q)  # type: ignore[arg-type]
    q.message.edit_text.assert_awaited_once_with(t("ru", "delete.done"))  # answered in the language being erased
    assert (await app.store.get_account(101))["coins"] == 0
    assert await app.store.get_lang(101) == "uz"
    p = (await app.store.load(done.id)).by_user(101)
    assert p.first_name == "—" and p.username is None
    # Other players keep their names.
    assert (await app.store.load(done.id)).by_user(102).first_name == "P2"


@pytest.mark.asyncio
async def test_delete_is_refused_during_a_game(app: App) -> None:
    await app.store.credit_wallet(101, "P1", coins=50)
    live = new_game(-100, 101)
    join(live, 101, "P1", None)
    await app.persist(live)
    q = _query("del:yes", 101)
    await botmod.cb_delete(q)  # type: ignore[arg-type]
    assert q.answer.await_args.kwargs["show_alert"] is True
    assert (await app.store.get_account(101))["coins"] == 50


@pytest.mark.asyncio
async def test_delete_cancel_keeps_everything(app: App) -> None:
    await app.store.credit_wallet(101, "P1", coins=50)
    q = _query("del:no", 101)
    await botmod.cb_delete(q)  # type: ignore[arg-type]
    q.message.edit_text.assert_awaited_once_with(t("uz", "delete.cancelled"))
    assert (await app.store.get_account(101))["coins"] == 50


def test_legal_commands_are_in_the_private_menu() -> None:
    _default, _group, private = botmod._bot_command_lists("uz")
    names = {c.command for c in private}
    assert {"privacy", "terms", "paysupport", "deletemydata"} <= names
