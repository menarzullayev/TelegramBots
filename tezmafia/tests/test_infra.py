from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from tezmafia.config import Settings
from tezmafia.db import Store
from tezmafia.engine import join, mark_dm_ok, new_game
from tezmafia.services.mute import apply_phase_mutes, unmute_all


@pytest.mark.asyncio
async def test_store_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    store = Store(f"sqlite+aiosqlite:///{tmp_path}/data/t.db")
    await store.init()
    g = new_game(9, 1)
    join(g, 1, "A", "a")
    mark_dm_ok(g, 1)
    await store.save(g)
    loaded = await store.load(g.id)
    assert loaded and loaded.players[0].username == "a"
    assert (await store.active_in_chat(9)).id == g.id
    assert (await store.by_user_lobby_or_live(1)).id == g.id
    assert (await store.by_user_lobby_or_live(2)) is None
    assert (await store.unfinished())[0].id == g.id
    assert (await store.games_for_user(1))[0].id == g.id
    assert await store.games_for_user(2) == []
    g.phase = "finished"
    await store.save(g)
    assert await store.active_in_chat(9) is None
    assert await store.load("missing") is None
    acc = await store.get_account(99)
    assert acc["coins"] == 0
    await store.credit_wallet(99, "Z", coins=40, gems=1)
    assert (await store.buy_item(99, "Z", "nope"))[1] == "no_item"
    assert (await store.buy_item(99, "Z", "shield"))[0]
    assert (await store.buy_item(99, "Z", "gun"))[1] == "no_money"
    assert (await store.get_account(99))["inventory"]["shield"] == 1
    await store.credit_wallet(99, "Z", coins=40)
    assert (await store.buy_item(99, "Z", "gun"))[0]
    skipped = await store.take_loadout(99, skip={"gun"})
    assert skipped["gun"] is False
    assert skipped["shield"] is True
    assert (await store.get_account(99))["inventory"].get("gun") == 1
    flags = await store.take_loadout(99)
    assert flags["gun"] is True
    assert flags["shield"] is False
    assert (await store.get_account(99))["inventory"] == {}
    await store.bump_stat(99, "Z", True)
    wallet = await store.get_account(99)
    assert wallet["coins"] >= 35
    assert wallet["gems"] >= 1
    empty = await store.take_loadout(7)
    assert empty["gun"] is False
    await store.buy_item(8, "New", "mask")
    assert (await store.get_account(8))["coins"] == 0
    assert (await store.buy_next_role(8, "New", "detective"))[1] == "no_money"
    await store.credit_wallet(8, "New", coins=35)
    assert (await store.buy_next_role(8, "New", "detective"))[0]
    assert (await store.get_account(8))["next_role"] == "detective"
    await store.credit_wallet(8, "New", coins=35)
    assert (await store.buy_next_role(8, "New", "mafia"))[1] == "already_queued"
    assert (await store.get_account(8))["next_role"] == "detective"
    assert await store.take_next_role(8) == "detective"
    assert await store.take_next_role(8) == ""
    assert await store.take_next_role(7) == ""
    assert await store.set_lang(1, "az") == "az"
    assert await store.get_lang(1) == "az"
    assert await store.set_lang(1, "br") == "br"
    assert await store.set_lang(1, "nope") == "uz"


def test_settings_defaults(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1:TEST")
    monkeypatch.setenv("BOT_USERNAME", "x")
    s = Settings()
    assert s.discussion_seconds == 90
    assert s.voting_seconds == 45
    assert s.database_url.startswith("sqlite")


def test_settings_rejects_non_sqlite(monkeypatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("BOT_TOKEN", "1:TEST")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://localhost/tezmafia")
    with pytest.raises(ValidationError, match="DECISION-01"):
        Settings()


@pytest.mark.asyncio
async def test_mutes() -> None:
    bot = MagicMock()
    bot.restrict_chat_member = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="no"))
    bot.get_chat_member = AsyncMock(
        return_value=SimpleNamespace(status=ChatMemberStatus.MEMBER)
    )
    bot.me = AsyncMock(return_value=SimpleNamespace(id=1))
    g = new_game(1, 1)
    join(g, 2, "A", None)
    await apply_phase_mutes(bot, g, night=True, enabled=False)
    await apply_phase_mutes(bot, g, night=True, enabled=True)
    bot.get_chat_member = AsyncMock(
        return_value=SimpleNamespace(status=ChatMemberStatus.ADMINISTRATOR)
    )
    bot.restrict_chat_member = AsyncMock()
    g.players[0].alive = False
    await apply_phase_mutes(bot, g, night=False, enabled=True)
    join(g, 3, "B", None)
    g.players[1].alive = True
    await apply_phase_mutes(bot, g, night=False, enabled=True)
    await apply_phase_mutes(bot, g, night=True, enabled=True)
    await unmute_all(bot, g)
    bot.get_chat_member = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="x"))
    await apply_phase_mutes(bot, g, night=True, enabled=True)
