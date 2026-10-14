import shutil

import pytest

from scripts import make_sticker_set as mss


def test_set_name_follows_bot_api_rule() -> None:
    assert mss.set_name("qorashahar_mafia_bot") == "raven_by_qorashahar_mafia_bot"


def test_every_shipped_sticker_has_an_emoji() -> None:
    files = mss.sticker_files()
    stickers = mss.input_stickers(files)
    assert [s.emoji_list for s in stickers] == list(mss.EMOJI.values())
    assert {s.format for s in stickers} == {"static"}


def test_missing_sticker_file_is_an_error(tmp_path) -> None:
    for f in mss.sticker_files()[1:]:
        shutil.copy(f, tmp_path / f.name)
    with pytest.raises(ValueError, match="do not match"):
        mss.sticker_files(tmp_path)


def test_unmapped_sticker_file_is_an_error(tmp_path) -> None:
    for f in mss.sticker_files():
        shutil.copy(f, tmp_path / f.name)
    (tmp_path / "s09-extra.webp").write_bytes(b"x")
    with pytest.raises(ValueError, match="do not match"):
        mss.sticker_files(tmp_path)
