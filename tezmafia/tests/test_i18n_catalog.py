import re

from tezmafia.engine import Phase
from tezmafia.i18n import ALLOWED, LANGS, TG_LANG, _load, cmd, missing_keys, phase_label, role_title, t
from tezmafia.roles import ROLE_UZ, Role
from tezmafia import texts


def _shape(value: str) -> tuple[list[str], list[str]]:
    """Runtime-relevant skeleton of a catalog string: placeholders and HTML tags."""
    return sorted(re.findall(r"\{(\w+)\}", value)), sorted(re.findall(r"</?(\w+)", value))


def catalog_mismatches(source: dict[str, str], other: dict[str, str]) -> list[str]:
    problems = [f"missing:{k}" for k in source if k not in other]
    problems += [f"extra:{k}" for k in other if k not in source]
    problems += [f"shape:{k}" for k, v in source.items() if k in other and _shape(v) != _shape(other[k])]
    return problems


def test_catalog_complete_for_all_langs() -> None:
    for lang in LANGS:
        assert missing_keys(lang) == []


def test_catalog_shape_matches_uz_for_all_langs() -> None:
    source = _load("uz")
    for lang in LANGS:
        assert catalog_mismatches(source, _load(lang)) == [], lang


def test_catalog_mismatches_catches_broken_entries() -> None:
    source = {"a": "Tun {n}", "b": "<b>{name}</b>", "c": "ok"}
    assert catalog_mismatches(source, dict(source)) == []
    assert catalog_mismatches(source, {"a": "Night {m}", "b": "<b>{name}</b>", "c": "ok"}) == ["shape:a"]
    assert catalog_mismatches(source, {"a": "Night {n}", "b": "{name}", "c": "ok"}) == ["shape:b"]
    assert catalog_mismatches(source, {"a": "Night {n}", "b": "<b>{name}</b>"}) == ["missing:c"]
    assert catalog_mismatches(source, {**source, "d": "x"}) == ["extra:d"]


def test_bot_profile_texts_fit_telegram_limits() -> None:
    # Bot API: short description <= 120 chars, description <= 512, command description 1..256.
    for lang in LANGS:
        assert 0 < len(t(lang, "profile.short")) <= 120, lang
        assert 0 < len(t(lang, "profile.desc")) <= 512, lang
        assert "/mafia" in t(lang, "profile.desc"), lang
        for key in ("mafia", "join", "status_dm", "buy", "help", "start"):
            assert 0 < len(cmd(lang, key)) <= 256, (lang, key)
            assert cmd(lang, key) != key, (lang, key)


def test_phase_labels_translated_for_all_langs() -> None:
    for lang in LANGS:
        for phase in Phase:
            label = phase_label(lang, phase.value)
            assert label and label != f"phase.{phase.value}", (lang, phase)
    assert phase_label("uz", Phase.NIGHT) != Phase.NIGHT.value


def test_role_titles_cover_21() -> None:
    assert len(ROLE_UZ) == 21
    for lang in ALLOWED:
        for role in Role:
            title = role_title(lang, role.value)
            assert title
            assert title != f"role.{role.value}"


def test_en_gameplay_differs_from_uz() -> None:
    assert role_title("en", "detective") in texts.role_card("detective", "en")
    assert role_title("uz", "detective") in texts.role_card("detective", "uz")
    assert role_title("en", "detective") != role_title("uz", "detective")
    assert t("en", "night.prompt", n=1) != t("uz", "night.prompt", n=1)
    assert t("en", "settings.body", label="x") != t("uz", "settings.body", label="x")
    assert "o‘zbekcha" not in texts.settings_text("uz").lower()


def test_cmd_menu_and_telegram_codes() -> None:
    assert TG_LANG["ua"] == "uk"
    assert TG_LANG["kz"] == "kk"
    assert TG_LANG["br"] == "pt"
    assert "Open a new game" == cmd("en", "mafia")
    assert cmd("uz", "mafia") != cmd("en", "mafia")
    for lang in LANGS:
        assert cmd(lang, "help")
        assert cmd(lang, "missing-cmd") == "missing-cmd"


def test_fallback_unknown_lang() -> None:
    assert t("xx", "btn.enter") == t("uz", "btn.enter")
    assert t("en", "missing.key.never") == "missing.key.never"
