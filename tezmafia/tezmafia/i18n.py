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

# Bot menu descriptions (DECISION-09). Separate from gameplay JSON catalog.
_CMD: dict[str, dict[str, str]] = {
    "mafia": {
        "uz": "Yangi o‘yin ochish",
        "en": "Open a new game",
        "ru": "Новая игра",
        "az": "Yeni oyun aç",
        "tr": "Yeni oyun aç",
        "ua": "Нова гра",
        "kz": "Жаңа ойын",
        "kg": "Жаңы оюн",
        "tj": "Бозии нав",
        "id": "Buka permainan baru",
        "br": "Abrir novo jogo",
    },
    "game": {
        "uz": "Yangi o‘yin",
        "en": "New game",
        "ru": "Новая игра",
        "az": "Yeni oyun",
        "tr": "Yeni oyun",
        "ua": "Нова гра",
        "kz": "Жаңа ойын",
        "kg": "Жаңы оюн",
        "tj": "Бозии нав",
        "id": "Permainan baru",
        "br": "Novo jogo",
    },
    "join": {
        "uz": "Lobbyga qo‘shilish",
        "en": "Join lobby",
        "ru": "Войти в лобби",
        "az": "Lobbeyə qoşul",
        "tr": "Lobiye katıl",
        "ua": "Долучитись до лобі",
        "kz": "Лоббиге кіру",
        "kg": "Лобиге кошул",
        "tj": "Ба лобби дароед",
        "id": "Gabung lobi",
        "br": "Entrar no lobby",
    },
    "leave": {
        "uz": "Lobbydan chiqish",
        "en": "Leave lobby",
        "ru": "Выйти из лобби",
        "az": "Lobbidən çıx",
        "tr": "Lobiden çık",
        "ua": "Вийти з лобі",
        "kz": "Лоббиден шығу",
        "kg": "Лобиден чык",
        "tj": "Аз лобби бароед",
        "id": "Keluar lobi",
        "br": "Sair do lobby",
    },
    "extend": {
        "uz": "Lobby vaqtini uzaytirish",
        "en": "Extend lobby time",
        "ru": "Продлить лобби",
        "az": "Lobbi vaxtını uzat",
        "tr": "Lobiyi uzat",
        "ua": "Продовжити лобі",
        "kz": "Лобби уақытын созу",
        "kg": "Лоби убактын узарт",
        "tj": "Вақти лоббиро дароз кунед",
        "id": "Perpanjang waktu lobi",
        "br": "Prolongar o lobby",
    },
    "next": {
        "uz": "Keyingi faza",
        "en": "Next phase",
        "ru": "Следующая фаза",
        "az": "Növbəti mərhələ",
        "tr": "Sonraki evre",
        "ua": "Наступна фаза",
        "kz": "Келесі кезең",
        "kg": "Кийинки фаза",
        "tj": "Марҳилаи навбатӣ",
        "id": "Fase berikutnya",
        "br": "Próxima fase",
    },
    "status": {
        "uz": "Holat",
        "en": "Status",
        "ru": "Статус",
        "az": "Status",
        "tr": "Durum",
        "ua": "Статус",
        "kz": "Күй",
        "kg": "Абал",
        "tj": "Ҳолат",
        "id": "Status",
        "br": "Status",
    },
    "status_dm": {
        "uz": "Mening o‘yinim",
        "en": "My game",
        "ru": "Моя игра",
        "az": "Oyunum",
        "tr": "Oyunum",
        "ua": "Моя гра",
        "kz": "Менің ойыным",
        "kg": "Менин оюнум",
        "tj": "Бозии ман",
        "id": "Permainan saya",
        "br": "Meu jogo",
    },
    "roles": {
        "uz": "Rollar",
        "en": "Roles",
        "ru": "Роли",
        "az": "Rollar",
        "tr": "Roller",
        "ua": "Ролі",
        "kz": "Рөлдер",
        "kg": "Ролдор",
        "tj": "Нақшҳо",
        "id": "Peran",
        "br": "Papéis",
    },
    "profile": {
        "uz": "Profil",
        "en": "Profile",
        "ru": "Профиль",
        "az": "Profil",
        "tr": "Profil",
        "ua": "Профіль",
        "kz": "Профиль",
        "kg": "Профиль",
        "tj": "Профил",
        "id": "Profil",
        "br": "Perfil",
    },
    "shop": {
        "uz": "Do‘kon",
        "en": "Shop",
        "ru": "Магазин",
        "az": "Mağaza",
        "tr": "Mağaza",
        "ua": "Крамниця",
        "kz": "Дүкен",
        "kg": "Дүкөн",
        "tj": "Мағоза",
        "id": "Toko",
        "br": "Loja",
    },
    "buy": {
        "uz": "Xarid: /buy maska",
        "en": "Buy: /buy mask",
        "ru": "Купить: /buy maska",
        "az": "Al: /buy maska",
        "tr": "Satın al: /buy maska",
        "ua": "Купити: /buy maska",
        "kz": "Сатып алу: /buy maska",
        "kg": "Сатып алуу: /buy maska",
        "tj": "Хarid: /buy maska",
        "id": "Beli: /buy maska",
        "br": "Comprar: /buy maska",
    },
    "top": {
        "uz": "Reyting",
        "en": "Leaderboard",
        "ru": "Рейтинг",
        "az": "Reytinq",
        "tr": "Sıralama",
        "ua": "Рейтинг",
        "kz": "Рейтинг",
        "kg": "Рейтинг",
        "tj": "Рейтинг",
        "id": "Peringkat",
        "br": "Ranking",
    },
    "settings": {
        "uz": "Til / sozlama",
        "en": "Language / settings",
        "ru": "Язык / настройки",
        "az": "Dil / ayarlar",
        "tr": "Dil / ayarlar",
        "ua": "Мова / налаштування",
        "kz": "Тіл / баптау",
        "kg": "Тил / жөндөө",
        "tj": "Забон / танзимот",
        "id": "Bahasa / pengaturan",
        "br": "Idioma / ajustes",
    },
    "stop": {
        "uz": "O‘yinni bekor qilish",
        "en": "Cancel the game",
        "ru": "Отменить игру",
        "az": "Oyunu ləğv et",
        "tr": "Oyunu iptal et",
        "ua": "Скасувати гру",
        "kz": "Ойынды тоқтату",
        "kg": "Оюнду жокко чыгар",
        "tj": "Бозиро бекор кунед",
        "id": "Batalkan permainan",
        "br": "Cancelar o jogo",
    },
    "help": {
        "uz": "Qoidalar",
        "en": "Rules",
        "ru": "Правила",
        "az": "Qaydalar",
        "tr": "Kurallar",
        "ua": "Правила",
        "kz": "Ережелер",
        "kg": "Эрежелер",
        "tj": "Қоидаҳо",
        "id": "Aturan",
        "br": "Regras",
    },
    "start": {
        "uz": "DM ochish",
        "en": "Open DM",
        "ru": "Открыть ЛС",
        "az": "DM aç",
        "tr": "DM aç",
        "ua": "Відкрити DM",
        "kz": "DM ашу",
        "kg": "DM ач",
        "tj": "DM кушоед",
        "id": "Buka DM",
        "br": "Abrir DM",
    },
}


def cmd(lang: str, key: str) -> str:
    lang = normalize_lang(lang)
    row = _CMD.get(key) or {}
    return row.get(lang) or row.get("uz") or key


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


def item_title(lang: str, key: str) -> str:
    return t(lang, f"item.{key}.title")


def item_desc(lang: str, key: str) -> str:
    return t(lang, f"item.{key}.desc")


def missing_keys(lang: str) -> list[str]:
    have = set(_load(normalize_lang(lang)))
    return sorted(catalog_keys() - have)
