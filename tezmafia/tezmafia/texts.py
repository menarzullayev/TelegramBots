from __future__ import annotations

from tezmafia.emoji import ce
from tezmafia.engine import Game
from tezmafia.i18n import item_desc, item_title, lang_label, role_card_body, role_dm_body, role_title, t
from tezmafia.roles import Role, bag_for


def lobby_text(game: Game, bot_username: str, lang: str = "uz") -> str:
    lines = [
        f"{ce('pin')} <b>{t(lang, 'lobby.title')}</b>",
        f"{ce('group')} {t(lang, 'lobby.slots', n=len(game.players), max=game.max_players, min=game.min_players)}",
        "",
    ]
    for p in game.players:
        mark = ce("check") if p.dm_ok else ce("hourglass")
        dm = t(lang, "lobby.dm_ok") if p.dm_ok else t(lang, "lobby.dm_wait")
        lines.append(f"{p.seat}. {p.html_label()} — {mark} {dm}")
    pending = [p for p in game.players if not p.dm_ok]
    if pending:
        lines.append("")
        lines.append(f"{ce('lock')} {t(lang, 'lobby.pending')}")
        lines.append(f"https://t.me/{bot_username}?start=g_{game.id}")
    else:
        lines.append("")
        lines.append(f"{ce('bolt')} {t(lang, 'lobby.ready')}")
    return "\n".join(lines)


def roles_public(game: Game, lang: str = "uz") -> str:
    bag = bag_for(len(game.players))
    bits = " · ".join(f"{n}: {c}" for n, c in bag.public_counts(lang))
    return f"{ce('lock')} <b>{t(lang, 'roles.public')}</b>\n{bits}"


def role_dm(game: Game, user_id: int, lang: str = "uz") -> str:
    p = game.by_user(user_id)
    if not p or not p.role:
        return f"{ce('warning')} {t(lang, 'role.empty')}"
    role = Role(p.role)
    title = role_title(lang, role.value)
    icon = {
        Role.MAFIA: "mafia",
        Role.DON: "mafia",
        Role.LAWYER: "mafia",
        Role.JOURNALIST: "mafia",
        Role.KILLER: "mafia",
        Role.DETECTIVE: "search",
        Role.SERGEANT: "search",
        Role.SNITCH: "search",
        Role.DOCTOR: "shield",
        Role.MANIAC: "death",
        Role.HOOKER: "wave",
        Role.SUICIDE: "warning",
        Role.HOBO: "door",
        Role.LUCKY: "bolt",
        Role.KAMIKAZE: "bolt",
        Role.MAGE: "bolt",
        Role.MAYOR: "pin",
        Role.WEREWOLF: "town",
        Role.ARSONIST: "warning",
        Role.CROOK: "info",
        Role.CITIZEN: "town",
    }.get(role, "town")
    lines = [f"{ce(icon)} <b>{t(lang, 'role.you', title=title)}</b>", role_dm_body(lang, role.value)]
    if role in (Role.MAFIA, Role.DON, Role.LAWYER, Role.JOURNALIST, Role.KILLER):
        lines.append(t(lang, "role.mates"))
        mates = [x.html_label() for x in game.alive_mafia() if x.user_id != user_id]
        lines.extend(f"• {m}" for m in mates or [t(lang, "role.alone")])
    return "\n".join(lines)


def night_prompt(game: Game, user_id: int, has_action: bool, lang: str = "uz") -> str:
    key = "night.prompt" if has_action else "night.idle"
    return f"{ce('night')} <b>{t(lang, key, n=game.round)}</b>"


def night_group(game: Game, lang: str = "uz") -> str:
    return f"{ce('night')} {t(lang, 'night.group', n=game.round)}"


def last_words(game: Game, seats: list[int] | None = None, lang: str = "uz") -> str:
    lines: list[str] = []
    for seat in seats if seats is not None else getattr(game, "afk_deaths", []) or []:
        p = game.by_seat(seat)
        if not p:
            continue
        if p.seat in getattr(game, "masked_deaths", []):
            who = p.html_label()
        else:
            role = role_title(lang, p.role) if p.role else "?"
            who = f"{p.html_label()} ({role})"
        lines.append(f"{ce('death')} {t(lang, 'last_words', who=who)}")
    return "\n".join(lines)


def day_group(game: Game, reveal: bool, lang: str = "uz") -> str:
    if game.night_miss:
        body = f"{ce('hourglass')} {t(lang, 'day.miss')}"
    elif game.night_saved:
        body = f"{ce('shield')} {t(lang, 'day.saved')}"
    elif game.last_death_seat:
        p = game.by_seat(game.last_death_seat)
        name = p.html_label() if p else f"#{game.last_death_seat}"
        extra = ""
        if reveal and game.last_death_role:
            extra = f"\n{ce('info')} {t(lang, 'day.reveal', role=role_title(lang, game.last_death_role))}"
        body = f"{ce('death')} {t(lang, 'day.death', name=name)}{extra}"
    else:
        body = f"{ce('day')} {t(lang, 'day.none')}"
    words = last_words(game, lang=lang)
    if words:
        body = f"{body}\n{words}"
    alive = ", ".join(p.html_label() for p in game.alive_players())
    return (
        f"{ce('day')} <b>{t(lang, 'day.title', n=game.round)}</b>\n{body}\n\n"
        f"{ce('group')} {t(lang, 'day.alive', alive=alive)}"
    )


def vote_group(game: Game, lang: str = "uz") -> str:
    return f"{ce('vote')} <b>{t(lang, 'vote.title')}</b>\n{t(lang, 'vote.body')}"


def vote_tally(game: Game, lang: str = "uz") -> str:
    head = vote_group(game, lang)
    lines = [head, ""]
    votes = [(p.html_label(), p.vote) for p in game.alive_players() if p.vote]
    if not votes:
        lines.append(f"{ce('hourglass')} {t(lang, 'vote.none')}")
        return "\n".join(lines)
    from collections import Counter

    counts = Counter(v for _, v in votes)
    for seat, n in counts.most_common():
        target = game.by_seat(seat)
        label = target.html_label() if target else f"#{seat}"
        lines.append(f"{ce('bolt')} {t(lang, 'vote.line', n=n, label=label)}")
    leftover = len(game.alive_players()) - len(votes)
    if leftover:
        lines.append(f"{ce('timer')} {t(lang, 'vote.leftover', n=leftover)}")
    return "\n".join(lines)


def elim_group(game: Game, tie: bool, reveal: bool, lang: str = "uz") -> str:
    if tie:
        return f"{ce('hourglass')} {t(lang, 'elim.tie')}"
    if not game.last_death_seat or game.last_death_cause != "vote":
        return f"{ce('hourglass')} {t(lang, 'elim.none')}"
    p = game.by_seat(game.last_death_seat)
    name = p.html_label() if p else "?"
    extra = ""
    if reveal and game.last_death_role:
        extra = f"\n{ce('info')} {t(lang, 'elim.role', role=role_title(lang, game.last_death_role))}"
    return f"{ce('death')} {t(lang, 'elim.out', name=name)}{extra}"


ROLE_CARDS: dict[str, tuple[str, str]] = {
    role.value: (role_title("uz", role.value), role_card_body("uz", role.value)) for role in Role
}


def roles_catalog(lang: str = "uz") -> str:
    return f"{ce('book')} <b>{t(lang, 'roles.catalog.title')}</b>\n{t(lang, 'roles.catalog.hint')}"


def role_card(key: str, lang: str = "uz") -> str:
    if key not in {r.value for r in Role}:
        return f"{ce('lock')} <b>?</b>\n{t(lang, 'card.unknown')}"
    return f"{ce('lock')} <b>{role_title(lang, key)}</b>\n{role_card_body(lang, key)}"


def help_html(lang: str = "uz") -> str:
    return f"{ce('book')} {t(lang, 'help.html')}"


def help_text(lang: str = "uz") -> str:
    return help_html(lang)


def start_reason(code: str, lang: str = "uz") -> str:
    key = {
        "not_lobby": "start.not_lobby",
        "too_few": "start.too_few",
        "dm_pending": "start.dm_pending",
    }.get(code)
    if not key:
        return code
    icon = {"not_lobby": "door", "too_few": "group", "dm_pending": "lock"}[code]
    return f"{ce(icon)} {t(lang, key)}"


def action_reason(code: str, lang: str = "uz") -> str:
    icons = {
        "not_night": "night",
        "not_voting": "vote",
        "dead": "death",
        "bad_target": "cross",
        "no_teamkill": "mafia",
        "no_action": "info",
        "no_self": "cancel",
        "cleared": "check",
        "lobby_closed": "door",
        "full": "group",
        "self_used": "shield",
        "blocked": "wave",
        "not_lynch": "vote",
        "not_lobby": "door",
        "no_extend": "timer",
        "no_first_shoot": "search",
        "no_item": "cancel",
        "no_money": "warning",
        "bought": "check",
        "already_queued": "info",
    }
    key = f"action.{code}"
    if code not in icons:
        return code
    return f"{ce(icons[code])} {t(lang, key)}"


def game_over(game: Game, lang: str = "uz") -> str:
    win_key = {
        "mafia": "go.mafia",
        "maniac": "go.maniac",
        "suicide": "go.suicide",
        "arsonist": "go.arsonist",
        "snitch": "go.snitch",
        "mage": "go.mage",
        "crook": "go.crook",
    }.get(game.winner or "", "go.town")
    icon = {
        "go.mafia": "mafia",
        "go.maniac": "death",
        "go.suicide": "warning",
        "go.arsonist": "warning",
        "go.snitch": "search",
        "go.mage": "bolt",
        "go.crook": "info",
        "go.town": "town",
    }[win_key]
    title = f"{ce(icon)} <b>{t(lang, win_key)}</b>"
    lines = [f"{ce('party')} <b>{t(lang, 'go.header')}</b>\n{title}"]
    words = last_words(game, lang=lang)
    if words:
        lines.extend(["", words])
    lines.extend(["", f"{ce('book')} {t(lang, 'go.roles')}"])
    for p in game.players:
        mark = t(lang, "alive") if p.alive else t(lang, "dead")
        role = role_title(lang, p.role) if p.role else "?"
        ico = ce("check") if p.alive else ce("death")
        lines.append(f"• {ico} {p.html_label()} — {role}, {mark}")
    return "\n".join(lines)


def game_over_short(game: Game, lang: str = "uz") -> str:
    key = {
        "mafia": "go.short.mafia",
        "maniac": "go.short.maniac",
        "suicide": "go.short.suicide",
        "arsonist": "go.short.arsonist",
        "snitch": "go.short.snitch",
        "mage": "go.short.mage",
        "crook": "go.short.crook",
    }.get(game.winner or "", "go.short.town")
    icon = {
        "go.short.mafia": "mafia",
        "go.short.maniac": "death",
        "go.short.suicide": "warning",
        "go.short.arsonist": "warning",
        "go.short.snitch": "search",
        "go.short.mage": "bolt",
        "go.short.crook": "info",
        "go.short.town": "town",
    }[key]
    return f"{ce(icon)} <b>{t(lang, 'go.header')}</b> — {t(lang, key)}"


def dm_opened(lang: str = "uz") -> str:
    return f"{ce('check')} {t(lang, 'dm.opened')}"


def cancelled(lang: str = "uz") -> str:
    return f"{ce('cancel')} {t(lang, 'cancelled')}"


def picked(label: str, lang: str = "uz") -> str:
    return f"{ce('check')} {t(lang, 'picked', label=label)}"


def voted(label: str, lang: str = "uz") -> str:
    return f"{ce('vote')} {t(lang, 'voted', label=label)}"


def lynch_text(game: Game, lang: str = "uz") -> str:
    p = game.by_seat(game.lynch_seat or -1)
    name = p.html_label() if p else "?"
    return f"{ce('vote')} <b>{t(lang, 'lynch.title')}</b>\n{t(lang, 'lynch.body', name=name)}"


def profile_text(
    name: str,
    games: int,
    wins: int,
    coins: int = 0,
    gems: int = 0,
    inventory: dict | None = None,
    next_role: str = "",
    lang: str = "uz",
) -> str:
    from tezmafia.shop import ITEMS

    lines = [
        f"{ce('search')} <b>{name}</b>",
        f"{ce('group')} {t(lang, 'profile.games', n=games)}",
        f"{ce('party')} {t(lang, 'profile.wins', n=wins)}",
        f"{ce('star')} {t(lang, 'profile.wallet', coins=coins, gems=gems)}",
    ]
    bag = []
    for key, n in (inventory or {}).items():
        title = item_title(lang, key) if key in ITEMS else key
        bag.append(f"{title}×{n}")
    if bag:
        lines.append(f"{ce('lock')} {t(lang, 'profile.bag', bag=', '.join(bag))}")
    else:
        lines.append(f"{ce('info')} {t(lang, 'profile.bag_empty')}")
    if next_role:
        try:
            title = role_title(lang, Role(next_role).value)
        except ValueError:
            title = next_role
        lines.append(f"{ce('book')} {t(lang, 'profile.next', title=title)}")
    return "\n".join(lines)


def shop_text(coins: int, gems: int, inventory: dict | None = None, lang: str = "uz") -> str:
    from tezmafia.shop import ITEMS

    lines = [
        f"{ce('star')} <b>{t(lang, 'shop.title')}</b>",
        t(lang, "shop.wallet", coins=coins, gems=gems),
        t(lang, "shop.howto"),
        "",
    ]
    for key, item in ITEMS.items():
        have = int((inventory or {}).get(key, 0) or 0)
        own = f" · {t(lang, 'shop.own', n=have)}" if have else ""
        lines.append(
            f"• <b>{item_title(lang, key)}</b> — ${item['cost']}{own}\n  {item_desc(lang, key)}"
        )
    return "\n".join(lines)


def top_text(rows: list[tuple[str, int, int]], lang: str = "uz") -> str:
    if not rows:
        return f"{ce('info')} {t(lang, 'top.empty')}"
    lines = [f"{ce('star')} <b>{t(lang, 'top.title')}</b>"]
    for i, (name, games, wins) in enumerate(rows, start=1):
        lines.append(t(lang, "top.row", i=i, name=name, wins=wins, games=games))
    return "\n".join(lines)


def settings_text(lang: str) -> str:
    return (
        f"{ce('info')} <b>{t(lang, 'settings.title')}</b>\n"
        f"{t(lang, 'settings.body', label=lang_label(lang))}"
    )


def lang_switched(lang: str) -> str:
    return f"{ce('check')} {t(lang, 'lang.switched', label=lang_label(lang))}"


def host_menu_text(lang: str = "uz") -> str:
    return f"{ce('lock')} {t(lang, 'host.menu')}"


def chats_text(n: int, lang: str = "uz") -> str:
    if n <= 0:
        return f"{ce('info')} {t(lang, 'chats.empty')}"
    return f"{ce('door')} {t(lang, 'chats.list', n=n)}"


def extended(seconds: int, lang: str = "uz") -> str:
    return f"{ce('timer')} {t(lang, 'extended', seconds=seconds)}"


def next_phase(lang: str = "uz") -> str:
    return f"{ce('bolt')} {t(lang, 'next_phase')}"


def detective_result(label: str, is_mafia: bool, lang: str = "uz") -> str:
    key = "detective.mafia" if is_mafia else "detective.town"
    icon = "mafia" if is_mafia else "town"
    return f"{ce(icon)} {t(lang, key, label=label)}"


def journalist_result(label: str, visitors: list[str], helper: bool, lang: str = "uz") -> str:
    who = ", ".join(visitors) if visitors else t(lang, "journalist.none")
    kind = t(lang, "journalist.helper") if helper else t(lang, "journalist.plain")
    return f"{ce('search')} {t(lang, 'journalist.line', label=label, who=who, kind=kind)}"
