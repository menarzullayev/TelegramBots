from __future__ import annotations

ITEMS: dict[str, dict[str, object]] = {
    "shield": {
        "cost": 25,
        "title": "Tun himoyasi",
        "desc": "Keyingi o‘yinda bitta tun o‘limidan saqlaydi.",
    },
    "vote_shield": {
        "cost": 30,
        "title": "Sud himoyasi",
        "desc": "Keyingi o‘yinda bir marta suddan qoladi.",
    },
    "mask": {
        "cost": 20,
        "title": "Maska",
        "desc": "O‘lganda rol ochilmaydi.",
    },
    "fake_id": {
        "cost": 20,
        "title": "Soxta hujjat",
        "desc": "Komissarga tinch ko‘rinasiz.",
    },
    "gun": {
        "cost": 40,
        "title": "Miltiq",
        "desc": "Tun roli bo‘lmasa — bir otish.",
    },
    "killer_shield": {
        "cost": 30,
        "title": "Qotildan himoya",
        "desc": "Keyingi o‘yinda qotil o‘qidan saqlaydi.",
    },
}

ALIASES = {
    "himoya": "shield",
    "qalqon": "shield",
    "tun": "shield",
    "sud": "vote_shield",
    "maska": "mask",
    "niqob": "mask",
    "hujjat": "fake_id",
    "miltiq": "gun",
    "to‘pponcha": "gun",
    "to'pponcha": "gun",
    "topponcha": "gun",
    "qotil": "killer_shield",
    "jallod": "killer_shield",
    "nimcha": "killer_shield",
}

ROLE_TICKET_COST = 35

# Telegram Stars products (currency XTR). Key -> (stars, coins). Bigger packs carry a bonus.
STAR_PACKS: dict[str, tuple[int, int]] = {
    "c100": (25, 100),
    "c450": (100, 450),
    "c1200": (250, 1200),
    "c2600": (500, 2600),
}
VIP_STARS = 150
VIP_PERIOD = 30 * 24 * 3600  # Telegram subscriptions are always 30 days
VIP_COIN_BONUS = 0.5
VIP_BADGE = "💎"

# Gem cosmetics: key -> (emoji, gems). Pure decoration, no gameplay effect.
BADGES: dict[str, tuple[str, int]] = {
    "star": ("⭐", 3),
    "rose": ("🌹", 5),
    "skull": ("💀", 5),
    "fire": ("🔥", 8),
    "crown": ("👑", 12),
}
# Badges that are won, never sold (shown in the gem shop only to their owners).
SPECIAL_BADGES: dict[str, tuple[str, int]] = {
    "trophy": ("🏆", 0),
    "founder": ("🎖", 0),
    "pass": ("🎟", 0),
    "recruiter": ("🤝", 0),
    "recruiter_month": ("🏅", 0),
}
# Role-card styles (DECISION-17): pre-rendered by scripts/make_skins.py, bought with gems.
SKINS: dict[str, str] = {"noir": "🖤", "gold": "🟨", "neon": "💜"}
SKIN_COST = 20
# Group premium (DECISION-17): a Stars subscription any member can pay for a group.
GROUP_PREMIUM_STARS = 199
PREMIUM_DAY_CHOICES = (60, 90, 120, 150, 180)
PREMIUM_NIGHT_CHOICES = (30, 45, 60, 90, 120)
PLAY_COINS = 10
WIN_COINS = 25
WIN_GEMS = 1


def empty_flags() -> dict[str, bool]:
    return {key: False for key in ITEMS}


def resolve_item(raw: str) -> str | None:
    key = raw.strip().lower().replace(" ", "_")
    key = ALIASES.get(key, key)
    return key if key in ITEMS else None


def resolve_role(raw: str) -> str | None:
    from tezmafia.i18n import ALLOWED, role_title
    from tezmafia.roles import ROLE_UZ, Role

    key = raw.strip().lower().replace("‘", "'")
    if key in {r.value for r in Role}:
        return key
    extras = {
        "komissar": "detective",
        "tinch": "citizen",
        "qora": "mafia",
        "aholi": "citizen",
        "commissar": "detective",
        "detective": "detective",
        "citizen": "citizen",
        "mafia": "mafia",
    }
    if key in extras:
        return extras[key]
    needle = key
    for role, title in ROLE_UZ.items():
        if title.lower().replace("‘", "'") == needle:
            return role.value
    for lang in ALLOWED:
        for role in Role:
            title = role_title(lang, role.value).lower().replace("‘", "'")
            if title == needle:
                return role.value
    return None
