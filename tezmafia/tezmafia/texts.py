from __future__ import annotations

from tezmafia.emoji import ce
from tezmafia.engine import Game
from tezmafia.i18n import item_desc, item_title, lang_label, role_card_body, role_dm_body, role_title, t
from tezmafia.roles import Role, bag_for


def countdown(deadline: float | None) -> str:
    """"⏳ in 45 seconds" style relative time; the inner text is the fallback for old clients."""
    if not deadline:
        return ""
    import time

    left = max(0, int(deadline - time.time()))
    return f'⏳ <tg-time unix="{int(deadline)}" format="r">{left}s</tg-time>'


def lobby_text(game: Game, bot_username: str, lang: str = "uz") -> str:
    lines = [
        f"{ce('pin')} <b>{t(lang, 'lobby.title')}</b>",
        f"{ce('group')} {t(lang, 'lobby.slots', n=len(game.players), max=game.max_players, min=game.min_players)}",
    ]
    if game.mode != "classic":
        lines.append(f"🎲 {t(lang, 'mode.' + game.mode)} — {t(lang, 'mode.' + game.mode + '.d')}")
    lines.append("")
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
    if game.deadline:
        lines.append(countdown(game.deadline))
    return "\n".join(lines)


def roles_public(game: Game, lang: str = "uz") -> str:
    if game.mode == "chaos" or game.disabled_roles:
        # Chaos deals a random set: count what was actually dealt, not the classic table.
        from collections import Counter

        dealt = Counter(p.role for p in game.players if p.role)
        bits = " · ".join(f"{role_title(lang, r)}: {c}" for r, c in dealt.most_common())
    else:
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
    text = f"{ce('night')} {t(lang, 'night.group', n=game.round)}"
    return f"{text}\n{countdown(game.deadline)}" if game.deadline else text


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
    text = (
        f"{ce('day')} <b>{t(lang, 'day.title', n=game.round)}</b>\n{body}\n\n"
        f"{ce('group')} {t(lang, 'day.alive', alive=alive)}"
    )
    return f"{text}\n{countdown(game.deadline)}" if game.deadline else text


def vote_group(game: Game, lang: str = "uz") -> str:
    return f"{ce('vote')} <b>{t(lang, 'vote.title')}</b>\n{t(lang, 'vote.body')}"


def vote_tally(game: Game, lang: str = "uz") -> str:
    head = vote_group(game, lang)
    lines = [head, ""]
    votes = [(p.html_label(), p.vote) for p in game.alive_players() if p.vote]
    if game.anon_vote:
        # Anonymous mode: only how many voted; the split stays hidden until the vote closes.
        lines.append(f"{ce('timer')} {t(lang, 'vote.anon', n=len(votes), m=len(game.alive_players()))}")
        return "\n".join(lines)
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


def date_tag(ts: float) -> str:
    """A date shown in the reader's own locale (date_time entity, short date)."""
    import time

    return f'<tg-time unix="{int(ts)}" format="d">{time.strftime("%Y-%m-%d", time.localtime(ts))}</tg-time>'


def profile_text(
    name: str,
    games: int,
    wins: int,
    coins: int = 0,
    gems: int = 0,
    inventory: dict | None = None,
    next_role: str = "",
    lang: str = "uz",
    vip_until: float | None = None,
    badge: str = "",
    xp: int = 0,
    achievements: int = 0,
) -> str:
    from html import escape

    from tezmafia.shop import ITEMS

    shown = f"{escape(badge)} {name}" if badge else name
    lines = [
        f"{ce('search')} <b>{shown}</b>",
        f"{ce('group')} {t(lang, 'profile.games', n=games)}",
        f"{ce('party')} {t(lang, 'profile.wins', n=wins)}",
        f"{ce('star')} {t(lang, 'profile.wallet', coins=coins, gems=gems)}",
    ]
    if vip_until:
        lines.append(f"💎 {t(lang, 'profile.vip', date=date_tag(vip_until))}")
    if xp or achievements:
        from tezmafia.progress import ACHIEVEMENTS, level_of

        lines.append(f"⭐ {t(lang, 'profile.level', level=level_of(xp), xp=xp)}")
        lines.append(f"🏅 {t(lang, 'profile.ach', n=achievements, total=len(ACHIEVEMENTS))}")
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
    lines += ["", f"💎 {t(lang, 'stars.vip_desc')}", f"<i>{t(lang, 'stars.note')}</i>"]
    return "\n".join(lines)


def gems_text(gems: int, lang: str = "uz") -> str:
    return f"{ce('party')} <b>{t(lang, 'gems.title')}</b>\n{t(lang, 'gems.body', gems=gems)}"


def top_text(rows: list[tuple[str, int, int]], lang: str = "uz", title: str | None = None) -> str:
    from html import escape

    if not rows:
        return f"{ce('info')} {t(lang, 'top.empty')}"
    lines = [f"{ce('star')} <b>{escape(title) if title else t(lang, 'top.title')}</b>"]
    for i, (name, games, wins) in enumerate(rows, start=1):
        lines.append(t(lang, "top.row", i=i, name=escape(name), wins=wins, games=games))
    return "\n".join(lines)


def history_text(games: list[Game], lang: str = "uz") -> str:
    if not games:
        return f"{ce('info')} {t(lang, 'history.empty')}"
    lines = [f"{ce('book')} <b>{t(lang, 'history.title')}</b>"]
    for g in games:
        result = t(lang, f"go.short.{g.winner}") if g.winner else t(lang, "history.cancelled")
        lines.append("• " + t(lang, "history.row", date=date_tag(g.created_at), result=result, n=len(g.players)))
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


def _legal_url(kind: str, lang: str) -> str:
    import json
    from pathlib import Path

    path = Path(__file__).with_name("legal_urls.json")
    try:
        urls = json.loads(path.read_text(encoding="utf-8")).get(kind, {})
    except (OSError, ValueError):
        return ""
    # Full pages exist in uz, ru, en; the other locales read the closest one.
    fallback = {"kg": "ru", "kz": "ru", "tj": "ru", "ua": "ru"}.get(lang, "en")
    return urls.get(lang) or urls.get(fallback) or urls.get("en", "")


def privacy_text(lang: str = "uz", days: int = 90) -> str:
    return f"{ce('lock')} {t(lang, 'legal.privacy', days=days, url=_legal_url('privacy', lang))}"


def terms_text(lang: str = "uz") -> str:
    return f"{ce('book')} {t(lang, 'legal.terms', url=_legal_url('terms', lang))}"


def game_over_rich(game: Game, lang: str = "uz") -> str:
    """Final roles as a rich-message table (Bot API 10.1); plain emoji only, no custom emoji tags."""
    from html import escape

    plain = {"mafia": "🔪", "maniac": "🩸", "suicide": "🎭", "arsonist": "🔥", "snitch": "🔎", "mage": "✨", "crook": "🃏"}
    win_key = {k: f"go.{k}" for k in plain}.get(game.winner or "", "go.town")
    head = f"<h3>🏆 {escape(t(lang, 'go.header'))}</h3><p><b>{plain.get(game.winner or '', '🏙')} {escape(t(lang, win_key))}</b></p>"
    rows = "".join(
        f"<tr><td>{p.seat}</td><td>{escape(p.first_name)}</td>"
        f"<td>{escape(role_title(lang, p.role) if p.role else '?')}</td>"
        f"<td>{'✅ ' + escape(t(lang, 'alive')) if p.alive else '💀 ' + escape(t(lang, 'dead'))}</td></tr>"
        for p in game.players
    )
    return f"{head}<table bordered striped><tr><th>#</th><th></th><th>{escape(t(lang, 'go.roles'))}</th><th></th></tr>{rows}</table>"


def config_text(cfg: dict, lang: str = "uz") -> str:
    def flag(on: bool) -> str:
        return "✅" if on else "❌"

    mode = cfg["mode"]
    body = t(
        lang,
        "config.body",
        mode=t(lang, f"mode.{mode}"),
        desc=t(lang, f"mode.{mode}.d"),
        reveal=flag(cfg["reveal"] and mode != "secret"),
        mute=flag(cfg["mute"]),
        day=cfg["day"],
        night=cfg["night"],
    )
    extra = t(lang, "config.extra", anon=flag(cfg.get("anon", False)), off=len(cfg.get("off", [])))
    return f"⚙️ <b>{t(lang, 'config.title')}</b>\n{body}\n{extra}"


def progress_dm(new_keys: list[str], level_up: int | None, lang: str = "uz") -> str:
    lines = [f"🏅 <b>{t(lang, 'ach.unlocked')}</b>: {t(lang, f'ach.{k}')}" for k in new_keys]
    if level_up:
        lines.append(f"⭐ <b>{t(lang, 'lvl.up', level=level_up)}</b>")
    return "\n".join(lines)
