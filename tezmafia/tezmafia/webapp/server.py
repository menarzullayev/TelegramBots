"""Mini App backend. Listens on localhost only; the public HTTPS name comes from a tunnel.

Every API call carries Telegram's initData in `Authorization: tma <initData>`. It is checked with
the bot token (HMAC, as Telegram documents) and must be younger than MAX_AGE, so nobody can read
or spend another user's wallet by guessing ids.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiogram.types import LabeledPrice
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web

from tezmafia.i18n import normalize_lang, t
from tezmafia.progress import ACHIEVEMENTS, XP_PER_LEVEL_STEP, level_of
from tezmafia.shop import BADGES, SPECIAL_BADGES, STAR_PACKS, VIP_PERIOD, VIP_STARS

if TYPE_CHECKING:
    from tezmafia.bot import App

log = logging.getLogger("tezmafia")
STATIC = Path(__file__).with_name("static")
MAX_AGE = 24 * 3600
APP_KEY = web.AppKey("tezmafia_app", object)


class RateLimit:
    """At most `limit` write calls per user per `window` seconds."""

    def __init__(self, limit: int = 10, window: float = 60.0) -> None:
        self.limit, self.window = limit, window
        self.hits: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        q = self.hits[user_id]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def authenticate(token: str, header: str | None, now: float | None = None) -> dict[str, Any] | None:
    """The Telegram user behind a request, or None if initData is missing, forged or stale."""
    if not header or not header.startswith("tma "):
        return None
    try:
        data = safe_parse_webapp_init_data(token, header[4:])
    except ValueError:
        return None
    if not data.user or (now or time.time()) - data.auth_date.timestamp() > MAX_AGE:
        return None
    return {"id": data.user.id, "first_name": data.user.first_name, "language_code": data.user.language_code}


_TAG = re.compile(r"<[^>]+>")


def plain(text: str) -> str:
    """Locale strings carry Telegram HTML; the page renders text, so tags and entities are dropped."""
    import html

    return html.unescape(_TAG.sub("", text))


def _next_level_xp(level: int) -> int:
    return XP_PER_LEVEL_STEP * level * level


async def build_state(app: App, user: dict[str, Any]) -> dict[str, Any]:
    uid = user["id"]
    stored = await app.store.get_lang(uid)
    lang = stored if stored != "uz" or not user.get("language_code") else normalize_lang(user["language_code"])
    acc = await app.store.get_account(uid)
    owned_badges = await app.store.owned_badges(uid)
    unlocked = await app.store.achievement_keys(uid)
    season = time.strftime("%Y-%m")
    level = level_of(acc["xp"])

    def plain_t(lang_: str, key: str, **kw: Any) -> str:
        return plain(t(lang_, key, **kw))

    def rows(items: list[tuple[str, int, int]]) -> list[dict[str, Any]]:
        return [{"name": n, "games": g, "wins": w} for n, g, w in items]

    return {
        "lang": lang,
        "strings": {
            key: plain_t(lang, key)
            for key in (
                "btn.profile", "app.tab_ach", "app.tab_top", "btn.shop", "btn.gems_shop", "btn.top_season", "btn.top_all",
                "stars.vip_desc", "stars.note", "app.paid", "app.error", "gems.no_gems", "gems.bought", "btn.badge_off",
                "top.empty", "cmd.privacy", "cmd.terms", "app.tab_games", "chr.empty",
            )
        },
        "profile": {
            "name": acc["name"] or user["first_name"],
            "badge": acc["badge"],
            "games": acc["games"],
            "wins": acc["wins"],
            "coins": acc["coins"],
            "gems": acc["gems"],
            "xp": acc["xp"],
            "level": level,
            "level_from": _next_level_xp(level - 1),
            "level_to": _next_level_xp(level),
            "vip_until": acc["vip_until"],
            "lines": {
                "games": plain_t(lang, "profile.games", n=acc["games"]),
                "wins": plain_t(lang, "profile.wins", n=acc["wins"]),
                "wallet": plain_t(lang, "profile.wallet", coins=acc["coins"], gems=acc["gems"]),
                "level": plain_t(lang, "profile.level", level=level, xp=acc["xp"]),
                "ach": plain_t(lang, "profile.ach", n=len(unlocked), total=len(ACHIEVEMENTS)),
                "fair": plain_t(lang, "profile.fair", score=await app.store.fair_play(uid)),
            },
        },
        "achievements": [{"key": k, "title": plain_t(lang, f"ach.{k}"), "unlocked": k in unlocked} for k in ACHIEVEMENTS],
        "top": {
            "season": {"title": plain_t(lang, "top.season", season=season), "rows": rows(await app.store.cached(("season", season, 0), lambda: app.store.season_top(season)))},
            "all": {"title": plain_t(lang, "btn.top_all"), "rows": rows(await app.store.cached(("top_all",), app.store.top_stats))},
        },
        "shop": {
            "packs": [
                {"key": k, "stars": s, "coins": c, "label": plain_t(lang, "btn.stars_pack", coins=c, stars=s)}
                for k, (s, c) in STAR_PACKS.items()
            ],
            "vip": {"key": "vip", "stars": VIP_STARS, "label": plain_t(lang, "btn.vip", stars=VIP_STARS)},
        },
        "badges": [
            {
                "key": k, "emoji": e, "cost": c, "owned": k in owned_badges, "worn": acc["badge"] == e,
                "label": plain_t(lang, "btn.badge_wear", icon=e) if k in owned_badges
                else plain_t(lang, "btn.badge_buy", icon=e, cost=c),
            }
            for k, (e, c) in {**BADGES, **{k: v for k, v in SPECIAL_BADGES.items() if k in owned_badges}}.items()
        ],
        "gems_body": plain_t(lang, "gems.body", gems=acc["gems"]),
        "games": [chronicle_entry(g, uid, lang) for g in await app.store.user_games(uid, limit=10)],
    }


def chronicle_entry(game: Any, uid: int, lang: str) -> dict[str, Any]:
    from tezmafia.engine import player_won
    from tezmafia.i18n import role_title
    from tezmafia.texts import chronicle_lines

    me = game.by_user(uid)
    won = bool(me and player_won(game, me))
    you = ""
    if me:
        role = role_title(lang, me.role) if me.role else "?"
        you = plain(t(lang, "chr.you", role=role, result=t(lang, "card.draw" if game.winner == "draw" else "card.win" if won else "card.loss")))
    return {
        "id": game.id,
        "at": game.created_at,
        "players": len(game.players),
        "result": plain(t(lang, f"go.short.{game.winner}")) if game.winner else plain(t(lang, "history.cancelled")),
        "you": you,
        "won": won,
        "events": [plain(line) for line in chronicle_lines(game, lang)],
    }


def _user(request: web.Request) -> dict[str, Any]:
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    user = authenticate(app.settings.bot_token, request.headers.get("Authorization"))
    if not user:
        raise web.HTTPUnauthorized(text="bad init data")
    return user


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


async def state(request: web.Request) -> web.Response:
    user = _user(request)
    return web.json_response(await build_state(request.app[APP_KEY], user))  # type: ignore[arg-type]


async def invoice(request: web.Request) -> web.Response:
    user = _user(request)
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    if not request.app["limits"].allow(user["id"]):
        raise web.HTTPTooManyRequests()
    body = await request.json()
    key = str(body.get("product", ""))
    lang = await app.store.get_lang(user["id"])
    if key == "vip":
        title, desc, stars, extra = "TezMafia VIP", t(lang, "stars.inv_desc_vip"), VIP_STARS, {"subscription_period": VIP_PERIOD}
    elif key in STAR_PACKS:
        stars, coins = STAR_PACKS[key]
        title, desc, extra = t(lang, "stars.inv_title_pack", coins=coins), t(lang, "stars.inv_desc_pack", coins=coins), {}
    else:
        raise web.HTTPBadRequest(text="unknown product")
    link = await app.bot.create_invoice_link(
        title=title, description=desc, payload=f"{key}:{user['id']}", currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)], **extra,
    )
    return web.json_response({"link": link})


async def badge(request: web.Request) -> web.Response:
    user = _user(request)
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    if not request.app["limits"].allow(user["id"]):
        raise web.HTTPTooManyRequests()
    body = await request.json()
    key = str(body.get("key", ""))
    if key == "off":
        await app.store.take_off_badge(user["id"])
        result = "removed"
    elif key in BADGES or key in SPECIAL_BADGES:
        result = await app.store.buy_badge(user["id"], user["first_name"], key)
    else:
        raise web.HTTPBadRequest(text="unknown badge")
    return web.json_response({"result": result, "state": await build_state(app, user)})


@web.middleware
async def security_headers(request: web.Request, handler: Any) -> web.StreamResponse:
    resp = await handler(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


def build_app(app: App) -> web.Application:
    web_app = web.Application(middlewares=[security_headers], client_max_size=16 * 1024)
    web_app[APP_KEY] = app
    web_app["limits"] = RateLimit()
    web_app.add_routes(
        [
            web.get("/", index),
            web.get("/api/state", state),
            web.post("/api/invoice", invoice),
            web.post("/api/badge", badge),
        ]
    )
    return web_app


async def start_server(app: App, port: int) -> web.AppRunner:
    runner = web.AppRunner(build_app(app), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    log.info("mini app listening on 127.0.0.1:%s", port)
    return runner


def dumps(data: Any) -> str:  # pragma: no cover - debugging helper
    return json.dumps(data, ensure_ascii=False, indent=2)
