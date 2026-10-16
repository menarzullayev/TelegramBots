"""Local design preview of the Mini App page with sample data (no Telegram, no auth, no bot token).

Usage (from the tezmafia directory):  python -m scripts.webapp_preview  -> http://127.0.0.1:8797
"""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from aiohttp import web

from tezmafia.db import Store
from tezmafia.webapp.server import STATIC, asset, build_state, font


async def main(port: int = 8797) -> None:
    tmp = Path(tempfile.mkdtemp())
    store = Store(f"sqlite+aiosqlite:///{tmp}/preview.db")
    await store.init()
    for uid, name, wins in [(7, "Saidakbar", 6), (8, "Nodir", 4), (9, "Dilnoza", 3)]:
        for i in range(10):
            await store.bump_stat(uid, name, won=i < wins, alive=i % 2 == 0)
            await store.bump_season("2026-10", -1, uid, name, i < wins)
    await store.credit_wallet(7, "Saidakbar", coins=320, gems=9)
    await store.buy_badge(7, "Saidakbar", "rose")
    await store.buy_skin(7, "Saidakbar", "gold", 0)
    await store.quest_advance(time.strftime("%Y-%m-%d"), 7, {"play_2": 1, "play_3": 1, "win_1": 1, "win_2": 1,
                              "survive_1": 1, "win_town": 1})
    await store.credit_wallet(8, "Nodir", coins=200)
    await store.create_clan(7, "Saidakbar", "Qora Qarg‘a", 0)
    await store.join_clan(8, "qora qarg‘a", 30)
    from tezmafia.social import week_key

    for uid, name, pts in [(7, "Saidakbar", 22), (8, "Nodir", 17), (9, "Dilnoza", 9)]:
        for _ in range(pts // 4):
            await store.bump_week(week_key(), uid, name, True, 4)
    await store.award(7, {"first_game", "games_10", "first_win", "survivor", "win_mafia"})
    from tezmafia.engine import Phase, join, mark_dm_ok, new_game, start

    game = new_game(-1, 7)
    for uid, name in [(7, "Saidakbar"), (8, "Nodir"), (9, "Dilnoza"), (10, "Aziz"), (11, "Malika")]:
        join(game, uid, name, None)
        mark_dm_ok(game, uid)
    start(game)
    game.winner, game.phase = "town", Phase.FINISHED
    game.chronicle = [{"n": 1, "seat": 2, "cause": "night"}, {"n": 1, "seat": 4, "cause": "vote"},
                      {"n": 2, "seat": 3, "cause": "afk"}]
    await store.save(game)
    await store.link_game(game.id, [p.user_id for p in game.players])
    fake_app = SimpleNamespace(store=store)
    user = {"id": 7, "first_name": "Saidakbar", "language_code": "uz"}

    async def index(_r: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC / "index.html")

    async def state(_r: web.Request) -> web.Response:
        return web.json_response(await build_state(fake_app, user))  # type: ignore[arg-type]

    async def theme(r: web.Request) -> web.Response:
        from tezmafia.webapp.server import THEMES

        key = (await r.json()).get("theme")
        if key not in THEMES:
            raise web.HTTPBadRequest()
        await store.set_theme(7, key)
        return web.json_response({"result": "ok", "state": await build_state(fake_app, user)})  # type: ignore[arg-type]

    async def lang(r: web.Request) -> web.Response:
        from tezmafia.i18n import ALLOWED

        code = (await r.json()).get("lang")
        if code not in ALLOWED:
            raise web.HTTPBadRequest()
        await store.set_lang(7, code)
        return web.json_response({"result": "ok", "state": await build_state(fake_app, user)})  # type: ignore[arg-type]

    app = web.Application()
    app.add_routes([
        web.post("/api/lang", lang), web.get(r"/assets/fonts/{name:[a-z0-9-]+\.woff2}", font),
        web.get("/", index), web.get("/api/state", state), web.post("/api/theme", theme),
        web.get(r"/assets/{path:raven/(?:roles|skins/(?:noir|gold|neon))/[a-z_]+\.jpg}", asset),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    print(f"preview on http://127.0.0.1:{port}", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
