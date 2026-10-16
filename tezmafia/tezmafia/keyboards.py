from __future__ import annotations

from aiogram.types import CopyTextButton, DisabledButton, InlineKeyboardButton, InlineKeyboardMarkup

from tezmafia.emoji import icon
from tezmafia.engine import Game


def _btn(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    style: str | None = None,
    emoji: str | None = None,
    copy_text: str | None = None,
) -> InlineKeyboardButton:
    kwargs: dict = {"text": text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    if style:
        kwargs["style"] = style
    eid = icon(emoji) if emoji else None
    if eid:
        kwargs["icon_custom_emoji_id"] = eid
    if copy_text:
        kwargs["copy_text"] = CopyTextButton(text=copy_text)
    return InlineKeyboardButton(**kwargs)


def roles_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import role_title
    from tezmafia.roles import Role

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for role in Role:
        row.append(_btn(role_title(lang, role.value), callback_data=f"hr:{role.value}", emoji="book"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _start_button(game: Game, lang: str) -> InlineKeyboardButton:
    """Greyed out (Bot API 10.3 disabled button) until enough players sit at the table."""
    from tezmafia.i18n import t

    label = t(lang, "btn.start")
    if len(game.players) < game.min_players:
        eid = icon("bolt")
        extra = {"icon_custom_emoji_id": eid} if eid else {}
        return InlineKeyboardButton(
            text=f"{label} {len(game.players)}/{game.min_players}", disabled=DisabledButton(), **extra
        )
    return _btn(label, callback_data=f"s:{game.id}", style="success", emoji="bolt")


def my_role_kb(game: Game, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(t(lang, "btn.my_role"), callback_data=f"me:{game.id}", emoji="lock")]]
    )


def lobby_kb(game: Game, bot_username: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    deep = f"https://t.me/{bot_username}?start=g_{game.id}"
    add = add_group_url(bot_username)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn.join_dm"), url=deep, style="primary", emoji="door")],
            [
                _start_button(game, lang),
                _btn(t(lang, "btn.leave"), callback_data=f"l:{game.id}", style="danger", emoji="cancel"),
            ],
            [
                _btn(t(lang, "btn.link"), copy_text=deep, emoji="pin"),
                _btn(t(lang, "btn.add_group"), url=add, emoji="robot"),
            ],
            [_btn(t(lang, "btn.add_bot"), callback_data=f"ab:{game.id}", emoji="robot")],
        ]
    )


def player_buttons(
    game: Game,
    prefix: str,
    exclude_user: int | None = None,
    extra: list[list[InlineKeyboardButton]] | None = None,
    mark: str = "",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for p in game.alive_players():
        if exclude_user and p.user_id == exclude_user:
            continue
        row.append(
            _btn(
                f"{mark}{p.seat}. {p.first_name[:12]}",
                callback_data=f"{prefix}:{game.id}:{p.seat}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if extra:
        rows.extend(extra)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def night_kb(game: Game, user_id: int) -> InlineKeyboardMarkup:
    p = game.by_user(user_id)
    if not p or not p.role:
        return InlineKeyboardMarkup(inline_keyboard=[])
    if p.role in {"mafia", "don"}:
        return player_buttons(game, "nm", exclude_user=user_id)
    if p.role == "detective":
        check = player_buttons(game, "nd", exclude_user=user_id)
        if game.night_no <= 1:
            return check
        shoot = player_buttons(game, "ns", exclude_user=user_id, mark="🔫 ")
        return InlineKeyboardMarkup(inline_keyboard=check.inline_keyboard + shoot.inline_keyboard)
    if p.role == "doctor":
        return player_buttons(game, "np")
    if p.role == "maniac":
        return player_buttons(game, "nk", exclude_user=user_id)
    if p.role == "hooker":
        return player_buttons(game, "nh", exclude_user=user_id)
    if p.role == "lawyer":
        return player_buttons(game, "nl")
    if p.role == "hobo":
        return player_buttons(game, "nb", exclude_user=user_id)
    if p.role == "journalist":
        return player_buttons(game, "nj", exclude_user=user_id)
    if p.role == "killer":
        return player_buttons(game, "ni", exclude_user=user_id)
    if p.role == "arsonist":
        return player_buttons(game, "na")
    if p.role == "crook":
        return player_buttons(game, "nc", exclude_user=user_id)
    if p.role == "snitch":
        return player_buttons(game, "nt", exclude_user=user_id)
    if p.shop_gun:
        return player_buttons(game, "ng", exclude_user=user_id, mark="🔫 ")
    return InlineKeyboardMarkup(inline_keyboard=[])


def add_group_url(bot_username: str) -> str:
    return (
        f"https://t.me/{bot_username}?startgroup=mafia"
        "&admin=restrict_members+pin_messages+delete_messages+invite_users"
    )


def host_kb(bot_username: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn.add_group"), url=add_group_url(bot_username), emoji="robot")],
            [_btn(t(lang, "btn.enter"), callback_data="m:chats", style="primary", emoji="door")],
            [_btn(t(lang, "btn.lang"), callback_data="m:lang", emoji="info")],
            [
                _btn(t(lang, "btn.profile"), callback_data="m:profile", emoji="search"),
                _btn(t(lang, "btn.roles"), callback_data="m:roles", emoji="book"),
            ],
        ]
    )


def chats_kb(games: list[Game], bot_username: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import phase_label, t

    rows: list[list[InlineKeyboardButton]] = []
    for game in games[:8]:
        deep = f"https://t.me/{bot_username}?start=g_{game.id}"
        label = t(lang, "chats.table", phase=phase_label(lang, game.phase), n=len(game.players))
        rows.append([_btn(label, url=deep, emoji="door")])
    rows.append([_btn(t(lang, "btn.add_group"), url=add_group_url(bot_username), emoji="robot")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(t(lang, "btn.profile"), callback_data="m:profile", emoji="search"),
                _btn(t(lang, "btn.shop"), callback_data="m:shop", emoji="star"),
            ],
            [_btn(t(lang, "btn.enter"), callback_data="m:chats", emoji="door")],
            [
                _btn(t(lang, "btn.roles"), callback_data="m:roles", emoji="book"),
                _btn(t(lang, "btn.lang"), callback_data="m:lang", emoji="info"),
            ],
        ]
    )


def shop_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import item_title, t
    from tezmafia.shop import ITEMS, STAR_PACKS, VIP_STARS

    rows = [
        [_btn(f"{item_title(lang, key)} — ${item['cost']}", callback_data=f"buy:{key}", emoji="star")]
        for key, item in ITEMS.items()
    ]
    packs = [
        _btn(t(lang, "btn.stars_pack", coins=coins, stars=stars), callback_data=f"st:{key}", style="primary")
        for key, (stars, coins) in STAR_PACKS.items()
    ]
    rows += [packs[i : i + 2] for i in range(0, len(packs), 2)]
    rows.append([_btn(t(lang, "btn.vip", stars=VIP_STARS), callback_data="st:vip", style="success", emoji="star")])
    rows.append([_btn(t(lang, "btn.gems_shop"), callback_data="m:gems", emoji="party")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gems_kb(owned: list[str], worn: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t
    from tezmafia.shop import BADGES, SPECIAL_BADGES

    rows = []
    shown = {**BADGES, **{k: v for k, v in SPECIAL_BADGES.items() if k in owned}}
    for key, (emoji, cost) in shown.items():
        label = t(lang, "btn.badge_wear", icon=emoji) if key in owned else t(lang, "btn.badge_buy", icon=emoji, cost=cost)
        rows.append([_btn(label, callback_data=f"gb:{key}", style="success" if emoji == worn else None)])
    if worn:
        rows.append([_btn(t(lang, "btn.badge_off"), callback_data="gb:off", emoji="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def link_kb(text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(text, url=url, style="success", emoji="star")]])


def lynch_kb(game: Game, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(t(lang, "btn.lynch_yes"), callback_data=f"ly:{game.id}:1", style="danger", emoji="death"),
                _btn(t(lang, "btn.lynch_no"), callback_data=f"ly:{game.id}:0", style="success", emoji="check"),
            ]
        ]
    )


def lang_kb(lang: str = "uz", recruiter_hidden: bool | None = None) -> InlineKeyboardMarkup:
    """Language buttons; in a private chat `recruiter_hidden` adds the leaderboard visibility toggle."""
    from tezmafia.i18n import LANGS, t

    current = lang if lang in LANGS else "uz"
    rows = [
        [_btn(label, callback_data=f"lang:{code}", style="primary" if code == current else None)]
        for code, label in LANGS.items()
    ]
    if recruiter_hidden is not None:
        key = "btn.recruit_hidden" if recruiter_hidden else "btn.recruit_shown"
        rows.append([_btn(t(lang, key), callback_data="rec:toggle")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vote_kb(game: Game, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    skip = [_btn(t(lang, "btn.vote_clear"), callback_data=f"vx:{game.id}", style="danger", emoji="cancel")]
    return player_buttons(game, "v", extra=[skip])


def delete_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(t(lang, "btn.delete_yes"), callback_data="del:yes", style="danger", emoji="warning"),
                _btn(t(lang, "btn.delete_no"), callback_data="del:no", emoji="cancel"),
            ]
        ]
    )


def config_kb(cfg: dict, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    def mode_btn(key: str) -> InlineKeyboardButton:
        chosen = cfg["mode"] == key
        return _btn(("● " if chosen else "") + t(lang, f"mode.{key}"), callback_data=f"cfg:mode:{key}",
                    style="success" if chosen else None)

    def toggle(label: str, on: bool, key: str) -> InlineKeyboardButton:
        return _btn(f"{'✅' if on else '❌'} {label}", callback_data=f"cfg:{key}")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [mode_btn("classic"), mode_btn("chaos")],
            [mode_btn("secret"), mode_btn("fast")],
            [toggle(t(lang, "btn.cfg_reveal"), cfg["reveal"], "reveal"), toggle(t(lang, "btn.cfg_mute"), cfg["mute"], "mute")],
            [
                _btn(t(lang, "btn.cfg_day", n=cfg["day"]), callback_data="cfg:day", emoji="day"),
                _btn(t(lang, "btn.cfg_night", n=cfg["night"]), callback_data="cfg:night", emoji="night"),
            ],
            [
                toggle(t(lang, "btn.cfg_anon"), cfg.get("anon", False), "anon"),
                _btn(f"🎭 {t(lang, 'btn.cfg_roles')}", callback_data="cfg:roles"),
            ],
        ]
    )


def config_roles_kb(off: list[str], lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import role_title, t
    from tezmafia.roles import SPECIALS

    buttons = [
        _btn(f"{'❌' if key in off else '✅'} {role_title(lang, key)}", callback_data=f"cfr:{key}") for key in SPECIALS
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(t(lang, "btn.back"), callback_data="cfg:back", emoji="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rematch_kb(game: Game, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(t(lang, "btn.rematch"), callback_data=f"rm:{game.id}", style="success", emoji="bolt")]]
    )


def top_kb(view: str, in_group: bool, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    views = ["season", "group", "all", "recruit"] if in_group else ["season", "all", "recruit"]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(t(lang, f"btn.top_{v}"), callback_data=f"top:{v}", style="primary" if v == view else None)
                for v in views
            ]
        ]
    )


def remind_kb(schedule_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(t(lang, "btn.remind"), callback_data=f"sub:{schedule_id}", style="primary", emoji="timer")]]
    )


def invite_kb(link: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(inline_keyboard=[[_btn(t(lang, "btn.link"), copy_text=link, emoji="pin")]])


def pass_kb(claimable: int, premium: bool, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t
    from tezmafia.season_pass import PASS_STARS

    rows = []
    if claimable:
        rows.append([_btn(t(lang, "btn.pass_claim", n=claimable), callback_data="ps:claim", style="success")])
    if not premium:
        rows.append([_btn(t(lang, "btn.pass_buy", stars=PASS_STARS), callback_data="ps:buy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_kb(chat_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t
    from tezmafia.shop import GROUP_PREMIUM_STARS

    label = t(lang, "btn.premium_buy", stars=GROUP_PREMIUM_STARS)
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(label, callback_data=f"gp:{chat_id}", style="success")]])


def skins_kb(owned: list[str], worn: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t
    from tezmafia.shop import SKIN_COST, SKINS

    rows = []
    for key, mark in SKINS.items():
        name = f"{mark} {t(lang, f'skin.{key}')}"
        label = t(lang, "btn.skin_wear", name=name) if key in owned else t(lang, "btn.skin_buy", name=name, cost=SKIN_COST)
        rows.append([_btn(("✓ " if key == worn else "") + label, callback_data=f"sk:{key}")])
    if worn:
        rows.append([_btn(t(lang, "btn.skin_off"), callback_data="sk:off", emoji="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def share_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Opens the chat picker with the bot's inline mode pre-filled with "card"."""
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn.share"), switch_inline_query="card")]]
    )


def invite_inline_kb(bot_username: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn.add_group"), url=add_group_url(bot_username), emoji="robot")],
            [_btn(t(lang, "app.open"), url=f"https://t.me/{bot_username}?start=app", emoji="door")],
        ]
    )
