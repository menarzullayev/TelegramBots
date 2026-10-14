import pytest
from PIL import Image

from tezmafia import brand
from tezmafia.engine import Winner
from tezmafia.roles import Role


def test_every_media_file_ships() -> None:
    assert brand.missing_media() == []


def test_missing_media_reports_absent_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(brand, "ASSETS", tmp_path)
    missing = brand.missing_media()
    assert set(brand.MEDIA.values()) <= set(missing)
    assert "raven/roles/don.jpg" in missing
    target = tmp_path / brand.MEDIA["night"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    assert brand.MEDIA["night"] not in brand.missing_media()


def test_win_media_covers_every_winner() -> None:
    assert brand.win_media(Winner.MAFIA) == brand.MEDIA["win_mafia"]
    assert brand.win_media(Winner.TOWN) == brand.MEDIA["win_town"]
    assert brand.win_media(None) == brand.MEDIA["win_town"]
    assert brand.win_media(Winner.DRAW) == brand.MEDIA["night"]  # a draw is nobody's victory scene
    solo = [w for w in Winner if w not in (Winner.MAFIA, Winner.TOWN, Winner.DRAW)]
    assert solo
    for w in solo:
        assert brand.win_media(w) == brand.MEDIA[f"win_{w.value}"], w
    # Distinct scenes: no two winners share a picture.
    assert len({brand.win_media(w) for w in Winner}) == len(list(Winner))


def test_unknown_winner_falls_back_to_solo() -> None:
    assert brand.win_media("nobody") == brand.MEDIA["win_solo"]


def test_unknown_moment_is_an_error() -> None:
    with pytest.raises(KeyError):
        brand.media("no-such-moment")


def test_role_card_for_every_role() -> None:
    cards = {brand.role_card(r.value) for r in Role}
    assert None not in cards and len(cards) == len(list(Role))
    assert brand.role_card("no-such-role") is None
    assert brand.role_card("") is None


def test_caption_limit_counts_visible_text_only() -> None:
    assert brand.caption_fits("x" * brand.CAPTION_LIMIT)
    assert not brand.caption_fits("x" * (brand.CAPTION_LIMIT + 1))
    # Tags and entities do not count toward the limit.
    tagged = "<b>" + "y" * (brand.CAPTION_LIMIT - 1) + "</b>&amp;"
    assert brand.caption_fits(tagged)
    assert not brand.caption_fits(tagged + "z")


@pytest.mark.parametrize(
    ("moment", "size"),
    [("roles_dealt", (1280, 720)), ("menu_start", (1280, 720)), ("avatar", (640, 640))],
)
def test_photo_sizes(moment: str, size: tuple[int, int]) -> None:
    with Image.open(brand.ASSETS / brand.media(moment)) as im:
        assert im.size == size


def test_role_cards_are_square() -> None:
    for r in Role:
        with Image.open(brand.ASSETS / brand.role_card(r.value)) as im:
            assert im.size == (640, 640), r


def test_stickers_meet_telegram_spec() -> None:
    files = sorted((brand.ASSETS / "raven" / "stickers").glob("s0*.webp"))
    assert len(files) == 8
    for f in files:
        with Image.open(f) as im:
            assert im.size == (512, 512), f.name
            assert im.mode == "RGBA", f.name
            assert im.getchannel("A").getextrema()[0] == 0, f.name  # really transparent somewhere


def test_palette_is_hex() -> None:
    for name, value in brand.PALETTE.items():
        assert len(value) == 7 and value.startswith("#"), name
        int(value[1:], 16)
