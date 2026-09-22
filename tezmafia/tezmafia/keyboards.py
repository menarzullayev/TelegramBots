from __future__ import annotations

from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

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


def lobby_kb(game: Game, bot_username: str, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    deep = f"https://t.me/{bot_username}?start=g_{game.id}"
    add = add_group_url(bot_username)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(t(lang, "btn.join_dm"), url=deep, style="primary", emoji="door")],
            [
                _btn(t(lang, "btn.start"), callback_data=f"s:{game.id}", style="success", emoji="bolt"),
                _btn(t(lang, "btn.leave"), callback_data=f"l:{game.id}", style="danger", emoji="cancel"),
            ],
            [
                _btn(t(lang, "btn.link"), copy_text=deep, emoji="pin"),
                _btn(t(lang, "btn.add_group"), url=add, emoji="robot"),
            ],
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
    from tezmafia.i18n import t

    rows: list[list[InlineKeyboardButton]] = []
    for game in games[:8]:
        deep = f"https://t.me/{bot_username}?start=g_{game.id}"
        rows.append(
            [_btn(t(lang, "chats.table", phase=game.phase, n=len(game.players)), url=deep, emoji="door")]
        )
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
    from tezmafia.i18n import item_title
    from tezmafia.shop import ITEMS

    rows = [
        [_btn(f"{item_title(lang, key)} — ${item['cost']}", callback_data=f"buy:{key}", emoji="star")]
        for key, item in ITEMS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def lang_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import LANGS

    current = lang if lang in LANGS else "uz"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(label, callback_data=f"lang:{code}", style="primary" if code == current else None)]
            for code, label in LANGS.items()
        ]
    )


def vote_kb(game: Game, lang: str = "uz") -> InlineKeyboardMarkup:
    from tezmafia.i18n import t

    skip = [_btn(t(lang, "btn.vote_clear"), callback_data=f"vx:{game.id}", style="danger", emoji="cancel")]
    return player_buttons(game, "v", extra=[skip])
