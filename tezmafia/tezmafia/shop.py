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
    "tun": "shield",
    "sud": "vote_shield",
    "maska": "mask",
    "hujjat": "fake_id",
    "miltiq": "gun",
    "qotil": "killer_shield",
}

ROLE_TICKET_COST = 35
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
