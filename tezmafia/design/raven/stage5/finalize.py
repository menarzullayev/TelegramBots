"""Export the stage-5 menu headers (1280x720 JPG) and stickers (512x512 transparent PNG + WEBP),
plus a review sheet. Stickers are trimmed to their alpha bounds, then fitted into 512x512.

Usage: python finalize.py <downloads_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
HEADERS = [  # (download file, name, label)
    ("Raven Host at the Candlelit Threshold.png", "h01-start", "/start"),
    ("h02-help.png", "h02-help", "/help"),
    ("The Raven\u2019s Midnight Mask Bazaar.png", "h03-shop", "Qora bozor"),
    ("Raven Aristocrat Before the Gilded Mirror.png", "h04-profile", "Profil"),
    ("Raven King\u2019s Trophy Gallery.png", "h05-top", "Afsonalar"),
]
STICKERS = [
    ("Cheerful Raven Rogue Waving.png", "s01-hello", "Salom"),
    ("Cunning Raven in Crimson Regalia.png", "s02-suspicious", "Shubha"),
    ("Startled Raven in a Red Cloak.png", "s03-shocked", "Hayrat"),
    ("Laughing Regal Crow Sticker.png", "s04-laugh", "Kulgi"),
    ("Cozy Moonlit Raven Nap.png", "s05-sleep", "Uyqu"),
    ("Heroic Raven with Ornate Red Cape.png", "s06-vote", "Ovoz"),
    ("Celebratory Raven Sticker Mascot.png", "s07-victory", "G'alaba"),
    ("Melancholic Raven with Rose and Tear.png", "s08-farewell", "Xayr"),
]


def to_169(im: Image.Image) -> Image.Image:
    w, h = im.size
    if w / h > 16 / 9:
        nw = round(h * 16 / 9)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w * 9 / 16)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((1280, 720), Image.LANCZOS)


def to_sticker(im: Image.Image, size: int = 512, pad: int = 8) -> Image.Image:
    assert im.mode == "RGBA", "sticker must have a real alpha channel"
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
    scale = (size - 2 * pad) / max(im.size)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return out


def main(downloads: str) -> None:
    dl = Path(downloads)
    final = HERE / "final"
    final.mkdir(exist_ok=True)
    heads, stks = [], []
    for src, name, label in HEADERS:
        raw = Image.open(dl / src)
        raw.save(HERE / f"{name}.png")
        im = to_169(raw.convert("RGB"))
        im.save(final / f"{name}.jpg", quality=88, optimize=True, progressive=True)
        heads.append((label, im))
        print(f"{name}: {raw.size} -> 1280x720")
    for src, name, label in STICKERS:
        raw = Image.open(dl / src)
        raw.save(HERE / f"{name}.png")
        st = to_sticker(raw)
        st.save(final / f"{name}.png", optimize=True)
        st.save(final / f"{name}.webp", lossless=True)
        stks.append((label, st))
        print(f"{name}: {raw.size} {raw.mode} -> 512x512")

    font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 18)
    pad, cap, hw, hh, sw = 12, 28, 336, 189, 200
    width = 5 * hw + 6 * pad
    sheet = Image.new("RGB", (width, hh + cap + sw + cap + 3 * pad), "#101116")
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(heads):
        x = pad + i * (hw + pad)
        sheet.paste(im.resize((hw, hh), Image.LANCZOS), (x, pad))
        d.text((x, pad + hh + 4), f"H{i + 1:02d}  {label}", fill="#F1E9DB", font=font)
    y = 2 * pad + hh + cap
    sp = (width - 8 * sw) // 9
    for i, (label, st) in enumerate(stks):
        x = sp + i * (sw + sp)
        bg = Image.new("RGB", (sw, sw), "#1A1C23" if i % 2 else "#2A2C35")
        bg.paste(st.resize((sw, sw), Image.LANCZOS), (0, 0), st.resize((sw, sw), Image.LANCZOS))
        sheet.paste(bg, (x, y))
        d.text((x, y + sw + 4), f"S{i + 1:02d}  {label}", fill="#F1E9DB", font=font)
    sheet.save(HERE / "stage5-sheet.jpg", quality=85)
    print("sheet ->", HERE / "stage5-sheet.jpg")


if __name__ == "__main__":
    main(sys.argv[1])
