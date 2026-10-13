"""MafiaAz-parity language codes + catalog lookup (DECISION-06)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# Order matches @MafiaAzBot /start picker (2026-09-21).
LANGS: dict[str, str] = {
    "az": "🇦🇿 Azərbaycanca",
    "tr": "🇹🇷 Türkçe",
    "en": "🇺🇸 English",
    "ru": "🇷🇺 Русский",
    "ua": "🇺🇦 Український",
    "kz": "🇰🇿 Қазақ",
    "uz": "🇺🇿 O'zbek tili",
    "kg": "🇰🇬 Кыргызча",
    "tj": "🇹🇯 Тоҷикӣ",
    "id": "🇮🇩 Indonesia",
    "br": "🇧🇷 Português",
}

ALLOWED = frozenset(LANGS)
# Telegram Bot API language_code (ISO 639-1), not MafiaAz picker codes.
TG_LANG: dict[str, str] = {
    "az": "az",
    "tr": "tr",
    "en": "en",
    "ru": "ru",
    "ua": "uk",
    "kz": "kk",
    "uz": "uz",
    "kg": "ky",
    "tj": "tg",
    "id": "id",
    "br": "pt",
}

def cmd(lang: str, key: str) -> str:
    """Bot menu description (DECISION-09); unknown commands fall back to their own name."""
    full = f"cmd.{key}"
    text = t(lang, full)
    return key if text == full else text


_LOCALES = Path(__file__).resolve().parent / "locales"


def normalize_lang(raw: str) -> str:
    key = (raw or "").strip().lower()
    return key if key in ALLOWED else "uz"


def lang_label(code: str) -> str:
    return LANGS.get(normalize_lang(code), LANGS["uz"])


@lru_cache(maxsize=16)
def _load(lang: str) -> dict[str, str]:
    path = _LOCALES / f"{lang}.json"
    if not path.is_file():
        path = _LOCALES / "uz.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def catalog_keys() -> frozenset[str]:
    return frozenset(_load("uz"))


def t(lang: str, key: str, **kwargs: object) -> str:
    lang = normalize_lang(lang)
    table = _load(lang)
    raw = table.get(key)
    if raw is None and lang != "uz":
        raw = _load("uz").get(key)
    if raw is None:
        raw = key
    if kwargs:
        return raw.format(**kwargs)
    return raw


def role_title(lang: str, role: str) -> str:
    return t(lang, f"role.{role}")


def role_card_body(lang: str, role: str) -> str:
    return t(lang, f"role.{role}.card")


def role_dm_body(lang: str, role: str) -> str:
    return t(lang, f"role.{role}.dm")


def phase_label(lang: str, phase: str) -> str:
    return t(lang, f"phase.{phase}")


def item_title(lang: str, key: str) -> str:
    return t(lang, f"item.{key}.title")


def item_desc(lang: str, key: str) -> str:
    return t(lang, f"item.{key}.desc")


def missing_keys(lang: str) -> list[str]:
    have = set(_load(normalize_lang(lang)))
    return sorted(catalog_keys() - have)
