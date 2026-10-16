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

from tezmafia.i18n import ALLOWED, normalize_lang, t
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


# Native names, never translated; the order is the order of the picker.
LANG_NAMES = {
    "uz": "O‘zbekcha", "en": "English", "ru": "Русский", "az": "Azərbaycan", "br": "Português (BR)", "id": "Bahasa Indonesia",
    "kg": "Кыргызча", "kz": "Қазақша", "tj": "Тоҷикӣ", "tr": "Türkçe", "ua": "Українська",
}
FONT_DIR = "fonts"
THEMES = ("dossier", "neon", "deco", "day", "comic")  # all free; "dossier" is the default


def _next_level_xp(level: int) -> int:
    return XP_PER_LEVEL_STEP * level * level


async def build_state(app: App, user: dict[str, Any]) -> dict[str, Any]:
    uid = user["id"]
    # A language saved with /lang or the picker always wins (even "uz"); Telegram's language_code is only the first guess.
    stored = await app.store.lang_pref(uid)
    lang = stored or normalize_lang(user.get("language_code") or "")
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
        "languages": [{"code": k, "name": n} for k, n in LANG_NAMES.items()],
        "strings": {
            key: plain_t(lang, key)
            for key in (
                "btn.profile", "app.tab_ach", "app.tab_top", "btn.shop", "btn.gems_shop", "btn.top_season", "btn.top_all",
                "stars.vip_desc", "stars.note", "app.paid", "app.error", "gems.no_gems", "gems.bought", "btn.badge_off",
                "top.empty", "cmd.privacy", "cmd.terms", "app.tab_games", "chr.empty", "skins.title", "btn.skin_off",
                "app.tab_dossier", "app.tab_roles", "app.tab_wanted", "app.tab_log", "app.tab_market",
                "app.stamp", "app.field_name", "app.field_rank", "app.field_record", "app.field_wallet", "app.field_fair",
                "app.seals", "app.badges", "app.stars", "theme.title", "theme.hint", "top.recruit_empty",
                "lang.title", "app.close",
            )
        },
        "profile": {
            "name": acc["name"] or user["first_name"],
            "badge": acc["badge"],
            "title": plain_t(lang, "recruiter.title") if await app.store.has_ref_title(uid) else "",
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
                "fair_score": str(await app.store.fair_play(uid)),
                "record": plain_t(lang, "app.record", games=acc["games"], wins=acc["wins"]),
                "purse": plain_t(lang, "app.wallet", coins=acc["coins"], gems=acc["gems"]),
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
        "admin": await admin_state(app, uid, lang),
        "skins": await skins_state(app, uid, lang, acc["gems"]),
        "theme": await theme_of(app, uid),
        "themes": [{"id": k, "name": plain_t(lang, f"theme.{k}")} for k in THEMES],
        "case": plain_t(lang, "app.case", n=f"{uid % 100000:05d}"),
        "daily": await daily_state(app, uid, lang),
        "quests": await quests_state(app, uid, lang),
        "roles": await roles_state(app, uid, lang),
        "clan": await clan_state(app, uid, lang, season),
        "tournament": await tournament_state(app, uid, lang),
        "recruiters": await recruiters_state(app, uid, lang, season),
    }


def _today() -> tuple[str, str]:
    return time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))


async def daily_state(app: Any, uid: int, lang: str) -> dict[str, Any]:
    from tezmafia.retention import daily_reward, next_streak

    today, yesterday = _today()
    last, streak = await app.store.daily_state(uid)
    nxt = next_streak(last, today, yesterday, streak)
    coins, gems = daily_reward(nxt or streak or 1)
    return {
        "title": plain(t(lang, "app.daily")),
        "claimed": nxt is None,
        "streak": streak if nxt is None else (nxt - 1),
        "streak_text": plain(t(lang, "app.streak", n=streak if nxt is None else max(0, nxt - 1))),
        "button": plain(t(lang, "app.daily_claim", coins=coins)),
        "done": plain(t(lang, "app.daily_done")),
        "gem": bool(gems),
    }


async def quests_state(app: Any, uid: int, lang: str) -> dict[str, Any]:
    from tezmafia.retention import QUEST_COINS, QUEST_XP, QUESTS, todays_quests

    day = time.strftime("%Y-%m-%d")
    state = await app.store.quest_state(day, uid)
    items = []
    for key in todays_quests(day):
        target = QUESTS[key][0]
        progress, done = state.get(key, (0, False))
        items.append({"key": key, "title": plain(t(lang, f"q.{key}")), "progress": min(progress, target),
                      "target": target, "done": bool(done)})
    return {"title": plain(t(lang, "quests.title")), "items": items,
            "reward": plain(t(lang, "quests.reward", coins=QUEST_COINS, xp=QUEST_XP))}


async def roles_state(app: Any, uid: int, lang: str) -> dict[str, Any]:
    from tezmafia.brand import role_card
    from tezmafia.i18n import role_card_body, role_title
    from tezmafia.roles import ROLE_FACTION, Role

    skin = (await app.store.skins_of(uid))[0]
    items = [
        {"key": r.value, "title": plain(role_title(lang, r.value)), "body": plain(role_card_body(lang, r.value)),
         "side": ROLE_FACTION[r].value, "image": "/assets/" + (role_card(r.value, skin) or "")}
        for r in Role
    ]
    return {"intro": plain(t(lang, "app.roles_intro")), "items": items}


async def clan_state(app: Any, uid: int, lang: str, season: str) -> dict[str, Any]:
    from tezmafia.social import CLAN_MAX

    clan = await app.store.clan_of(uid)
    mine = None
    if clan:
        members, wins = await app.store.clan_stats(clan.id, season)
        mine = {"name": clan.name, "line": plain(t(lang, "app.clan_line", n=members, max=CLAN_MAX, wins=wins))}
    top = await app.store.cached(("clan_top", season), lambda: app.store.clan_top(season))
    return {"title": plain(t(lang, "app.clan")), "mine": mine, "none": plain(t(lang, "app.no_clan")),
            "top_title": plain(t(lang, "app.clans_top")),
            "top": [{"name": n, "members": m, "wins": w} for n, m, w in top[:5]]}


async def tournament_state(app: Any, uid: int, lang: str) -> dict[str, Any]:
    from tezmafia.social import week_key

    week = week_key()
    rows = await app.store.cached(("week", week), lambda: app.store.week_top(week))
    mine = next((p for u, _n, p in rows if u == uid), 0)
    return {"title": plain(t(lang, "app.tournament", week=week)), "me": plain(t(lang, "app.my_points", n=mine)),
            "rows": [{"name": n, "points": p, "me": u == uid} for u, n, p in rows[:10]]}


async def recruiters_state(app: Any, uid: int, lang: str, month: str) -> dict[str, Any]:
    rows = await app.store.cached(("recruit", month), lambda: app.store.recruiter_top(month, 10))
    tag = plain(t(lang, "recruiter.title"))
    return {"title": plain(t(lang, "top.recruit", month=month)),
            "rows": [{"name": (n or "—") + (f" 🤝 {tag}" if titled else ""), "n": c, "me": u == uid} for u, n, c, titled in rows]}


async def theme_of(app: Any, uid: int) -> str:
    chosen = await app.store.theme_of(uid)
    return chosen if chosen in THEMES else THEMES[0]


async def skins_state(app: Any, uid: int, lang: str, gems: int) -> dict[str, Any]:
    from tezmafia.shop import SKIN_COST, SKINS

    worn, owned = await app.store.skins_of(uid)
    items = []
    for key, icon in SKINS.items():
        name = f"{icon} {plain(t(lang, f'skin.{key}'))}"
        label = plain(t(lang, "btn.skin_wear", name=name)) if key in owned else plain(
            t(lang, "btn.skin_buy", name=name, cost=SKIN_COST))
        items.append({"key": key, "owned": key in owned, "worn": key == worn, "label": label})
    return {"body": plain(t(lang, "skins.body", cost=SKIN_COST, gems=gems)), "items": items, "worn": worn}


async def admin_state(app: Any, uid: int, lang: str) -> dict[str, Any] | None:
    """Owner-only funnel for the Mini App; everyone else gets None (the tab is not shown)."""
    from tezmafia.texts import funnel_lines

    settings = getattr(app, "settings", None)
    if not settings or not getattr(settings, "owner_id", None) or uid != settings.owner_id:
        return None
    f = await app.store.cached(("funnel7",), lambda: app.store.funnel(time.time() - 7 * 86400))
    return {"title": plain(t(lang, "funnel.title")), "tab": plain(t(lang, "app.tab_admin")),
            "lines": [plain(x) for x in funnel_lines(f, lang)]}


def chronicle_entry(game: Any, uid: int, lang: str) -> dict[str, Any]:
    from tezmafia.engine import player_won
    from tezmafia.i18n import role_title
    from tezmafia.texts import chronicle_lines, outcome_key

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
        "result": plain(t(lang, f"go.short.{outcome_key(game)}")) if game.winner else plain(t(lang, "history.cancelled")),
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
    # FileResponse adds ETag + Last-Modified and answers If-None-Match with 304; a minute of max-age skips even that.
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "public, max-age=60, must-revalidate"})


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


async def skin(request: web.Request) -> web.Response:
    from tezmafia.shop import SKIN_COST, SKINS

    user = _user(request)
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    if not request.app["limits"].allow(user["id"]):
        raise web.HTTPTooManyRequests()
    key = str((await request.json()).get("key", ""))
    if key == "off":
        await app.store.take_off_skin(user["id"])
        result = "removed"
    elif key in SKINS:
        result = await app.store.buy_skin(user["id"], user["first_name"], key, SKIN_COST)
    else:
        raise web.HTTPBadRequest(text="unknown skin")
    return web.json_response({"result": result, "state": await build_state(app, user)})


async def theme(request: web.Request) -> web.Response:
    user = _user(request)
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    if not request.app["limits"].allow(user["id"]):
        raise web.HTTPTooManyRequests()
    try:
        body = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="bad json") from None
    key = body.get("theme") if isinstance(body, dict) else None
    if not isinstance(key, str) or key not in THEMES:
        raise web.HTTPBadRequest(text="unknown theme")
    await app.store.set_theme(user["id"], key)
    return web.json_response({"result": "ok", "state": await build_state(app, user)})


async def set_language(request: web.Request) -> web.Response:
    user = _user(request)
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    if not request.app["limits"].allow(user["id"]):
        raise web.HTTPTooManyRequests()
    try:
        body = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="bad json") from None
    code = body.get("lang") if isinstance(body, dict) else None
    if not isinstance(code, str) or code not in ALLOWED:
        raise web.HTTPBadRequest(text="unknown language")
    await app.store.set_lang(user["id"], code)  # same store call as the bot's /lang buttons
    return web.json_response({"result": "ok", "state": await build_state(app, user)})


async def daily(request: web.Request) -> web.Response:
    user = _user(request)
    app: App = request.app[APP_KEY]  # type: ignore[assignment]
    if not request.app["limits"].allow(user["id"]):
        raise web.HTTPTooManyRequests()
    today, yesterday = _today()
    got = await app.store.claim_daily(user["id"], user["first_name"], today, yesterday)
    return web.json_response({"result": "claimed" if got else "already", "got": got, "state": await build_state(app, user)})


async def asset(request: web.Request) -> web.FileResponse:
    """Role portraits (and skins) for the role index; the route pattern only matches those files."""
    from tezmafia.brand import ASSETS

    path = ASSETS / request.match_info["path"]
    if not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800"})


async def font(request: web.Request) -> web.FileResponse:
    """Self-hosted woff2 files; the route pattern allows only a flat [a-z0-9-].woff2 name, so no path can escape."""
    from tezmafia.brand import ASSETS

    root = (ASSETS / FONT_DIR).resolve()
    path = (root / request.match_info["name"]).resolve()
    if path.parent != root or not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(
        path, headers={"Cache-Control": "public, max-age=31536000, immutable", "Content-Type": "font/woff2"}
    )


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
            web.post("/api/skin", skin),
            web.post("/api/theme", theme),
            web.post("/api/daily", daily),
            web.post("/api/lang", set_language),
            web.get("/assets/fonts/{name:[a-z0-9-]+\\.woff2}", font),
            web.get("/assets/{path:raven/(?:roles|skins/(?:noir|gold|neon))/[a-z_]+\\.jpg}", asset),
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
