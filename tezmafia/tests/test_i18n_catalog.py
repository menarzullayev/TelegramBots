from tezmafia.i18n import ALLOWED, LANGS, TG_LANG, cmd, missing_keys, role_title, t
from tezmafia.roles import ROLE_UZ, Role
from tezmafia import texts


def test_catalog_complete_for_all_langs() -> None:
    for lang in LANGS:
        assert missing_keys(lang) == []


def test_role_titles_cover_21() -> None:
    assert len(ROLE_UZ) == 21
    for lang in ALLOWED:
        for role in Role:
            title = role_title(lang, role.value)
            assert title
            assert title != f"role.{role.value}"


def test_en_gameplay_differs_from_uz() -> None:
    assert "Detective" in texts.role_card("detective", "en")
    assert "Komissar" in texts.role_card("detective", "uz")
    assert "Night" in t("en", "night.prompt", n=1)
    assert "Tun" in t("uz", "night.prompt", n=1)
    assert "Game text" in texts.settings_text("en")
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
