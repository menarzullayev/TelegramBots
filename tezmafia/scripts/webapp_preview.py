"""Local design preview of the Mini App page with sample data (no Telegram, no auth, no bot token).

Usage (from the tezmafia directory):  python -m scripts.webapp_preview  -> http://127.0.0.1:8797
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from aiohttp import web

from tezmafia.db import Store
from tezmafia.webapp.server import STATIC, build_state


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

    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/api/state", state)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    print(f"preview on http://127.0.0.1:{port}", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
