import pytest

from tezmafia import brand
from tezmafia.engine import Winner


def test_every_media_file_ships() -> None:
    assert brand.missing_media() == []


def test_missing_media_reports_absent_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(brand, "ASSETS", tmp_path)
    assert brand.missing_media() == sorted(set(brand.MEDIA.values()))
    (tmp_path / brand.MEDIA["night"]).write_bytes(b"x")
    assert brand.MEDIA["night"] not in brand.missing_media()


def test_win_media_covers_every_winner() -> None:
    assert brand.win_media(Winner.MAFIA) == brand.MEDIA["win_mafia"]
    assert brand.win_media(Winner.TOWN) == brand.MEDIA["win_town"]
    assert brand.win_media(None) == brand.MEDIA["win_town"]
    solo = [w for w in Winner if w not in (Winner.MAFIA, Winner.TOWN)]
    assert solo
    assert {brand.win_media(w) for w in solo} == {brand.MEDIA["win_solo"]}


def test_unknown_moment_is_an_error() -> None:
    with pytest.raises(KeyError):
        brand.media("no-such-moment")


def test_palette_is_hex() -> None:
    for name, value in brand.PALETTE.items():
        assert len(value) == 7 and value.startswith("#"), name
        int(value[1:], 16)
