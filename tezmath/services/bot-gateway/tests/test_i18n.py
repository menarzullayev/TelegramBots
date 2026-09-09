from middleware.i18n import t


def test_known_key_uz():
    result = t("uz", "processing")
    assert "yechilmoqda" in result


def test_known_key_ru():
    result = t("ru", "processing")
    assert "Решаю" in result


def test_missing_lang_falls_back_to_uz():
    result = t("fr", "processing")
    assert result == t("uz", "processing")


def test_format_params():
    result = t("uz", "limit_exceeded", limit=5)
    assert "5" in result


def test_missing_key_returns_key():
    result = t("uz", "nonexistent_key_xyz")
    assert result == "nonexistent_key_xyz"
