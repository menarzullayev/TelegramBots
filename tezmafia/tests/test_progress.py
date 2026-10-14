"""F5b: XP, levels and achievements."""

from __future__ import annotations

import pytest

from tests.test_bot_e2e import FakeBot, _ready_game, _settings
from tezmafia import bot as botmod
from tezmafia import texts
from tezmafia.bot import App
from tezmafia.db import Store
from tezmafia.engine import start
from tezmafia.i18n import LANGS, t
from tezmafia.progress import ACHIEVEMENTS, Outcome, earned, level_of, xp_for


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


def test_levels_grow_slower_as_xp_grows() -> None:
    assert [level_of(x) for x in (0, 49, 50, 199, 200, 450, 800)] == [1, 1, 2, 2, 3, 4, 5]
    assert level_of(-10) == 1


def test_xp_rewards_playing_winning_and_surviving() -> None:
    assert xp_for(False, False) == 10
    assert xp_for(True, False) == 30
    assert xp_for(True, True) == 35


def _outcome(**kw) -> Outcome:
    base = dict(role="citizen", faction="town", winner="town", won=False, alive=False, games=1, wins=0, xp=10)
    base.update(kw)
    return Outcome(**base)


def test_achievement_rules() -> None:
    assert earned(_outcome()) == {"first_game"}
    assert {"first_win", "survivor"} <= earned(_outcome(won=True, alive=True, wins=1))
    assert "win_don" in earned(_outcome(role="don", faction="mafia", winner="mafia", won=True, wins=1))
    assert "win_solo" in earned(_outcome(role="maniac", faction="neutral", winner="maniac", won=True, wins=1))
    assert "win_solo" not in earned(_outcome(won=True, wins=1))  # town win is not solo
    assert "level_5" in earned(_outcome(xp=800))


def test_every_achievement_has_a_name_in_every_language() -> None:
    for lang in LANGS:
        for key in ACHIEVEMENTS:
            assert t(lang, f"ach.{key}") != f"ach.{key}", (lang, key)


@pytest.mark.asyncio
async def test_game_end_awards_once_and_dms_only_news(app: App) -> None:
    g = _ready_game()
    start(g)
    g.winner = "town"
    dms: list[tuple[int, str]] = []

    async def dm(user_id, text, **k):
        dms.append((user_id, text))
        return True

    app.dm = dm  # type: ignore[method-assign]

    def captions() -> dict[int, str]:
        return {c[1][0]: c[2].get("caption", "") for c in app.bot.calls if c[0] == "send_photo"}

    await app.record_stats(g)
    assert dms == []  # the news rides on the result card, not a second message
    assert set(captions()) == {p.user_id for p in g.players}
    assert all(t("uz", "ach.first_game") in text for text in captions().values())
    assert await app.store.achievement_count(g.players[0].user_id) >= 1

    app.bot.calls.clear()
    await app.record_stats(g)  # second game: first_game is not news any more
    assert all(t("uz", "ach.first_game") not in text for text in captions().values())


@pytest.mark.asyncio
async def test_award_returns_only_new_keys(app: App) -> None:
    assert await app.store.award(7, {"first_game", "first_win"}) == ["first_game", "first_win"]
    assert await app.store.award(7, {"first_game", "survivor"}) == ["survivor"]
    assert await app.store.achievement_count(7) == 3
    await app.store.delete_user(7)
    assert await app.store.achievement_count(7) == 0


@pytest.mark.asyncio
async def test_bump_stat_returns_totals_with_xp(app: App) -> None:
    first = await app.store.bump_stat(7, "U", won=True, alive=True)
    assert first == {"games": 1, "wins": 1, "xp": 35}
    second = await app.store.bump_stat(7, "U", won=False)
    assert second == {"games": 2, "wins": 1, "xp": 45}


def test_profile_shows_level_and_achievements() -> None:
    text = texts.profile_text("A", 3, 1, xp=260, achievements=4)
    assert t("uz", "profile.level", level=3, xp=260) in text
    assert t("uz", "profile.ach", n=4, total=len(ACHIEVEMENTS)) in text
    assert t("uz", "profile.level", level=1, xp=0) not in texts.profile_text("A", 0, 0)


def test_progress_dm_lists_news_and_level() -> None:
    text = texts.progress_dm(["first_win"], 2)
    assert t("uz", "ach.first_win") in text and t("uz", "lvl.up", level=2) in text
