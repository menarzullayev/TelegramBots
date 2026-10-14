"""Name, crop to 16:9 and export the 16 stage-3 frames as 1280x720 JPGs, plus a review sheet.

Usage: python finalize.py <downloads_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
LATER = [  # downloads after the crash, in generation order
    ("Raven Chancellor Sealing the Decree.png", "f08-verdict-sealed"),
    ("Raven King Over the Crimson City.png", "f09-win-mafia"),
    ("Raven Herald Over the Golden City.png", "f10-win-town"),
    ("Raven Over the Crimson Moon.png", "f11-win-maniac"),
    ("Masked Trickster Beneath the Raven\u2019s Gaze.png", "f12-win-suicide"),
    ("Raven Over the Burning City.png", "f13-win-arsonist"),
    ("Raven and Rogue Over the Map.png", "f14-win-snitch"),
    ("Moonlit Gothic Spellbound Duel.png", "f15-win-mage"),
    ("Raven Behind the Crimson Curtain.png", "f16-win-crook"),
]
LABELS = {
    "f01": "Stol ochildi", "f02": "Rollar tarqatildi", "f03": "Tun", "f04": "Tong",
    "f05": "Tong, qurbon", "f06": "Sud", "f07": "Hukm tasdig'i", "f08": "Hukm muhri",
    "f09": "Mafiya g'alabasi", "f10": "Shahar g'alabasi", "f11": "Manyak", "f12": "Suitsid",
    "f13": "Arsonist", "f14": "Ayg'oqchi", "f15": "Afsungar", "f16": "Firibgar",
}


def to_169(im: Image.Image) -> Image.Image:
    w, h = im.size
    if w / h > 16 / 9:
        nw = round(h * 16 / 9)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w * 9 / 16)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((1280, 720), Image.LANCZOS)


def main(downloads: str) -> None:
    dl = Path(downloads)
    for src, name in LATER:
        Image.open(dl / src).save(HERE / f"{name}.png")
    out = HERE / "final"
    out.mkdir(exist_ok=True)
    frames = sorted(HERE.glob("f[0-9][0-9]-*.png"))
    assert len(frames) == 16, [f.name for f in frames]
    thumbs = []
    for f in frames:
        im = to_169(Image.open(f).convert("RGB"))
        im.save(out / f"{f.stem}.jpg", quality=88, optimize=True, progressive=True)
        thumbs.append((f.stem, im))
        print(f"{f.stem}: {Image.open(f).size} -> 1280x720")

    tw, th, pad, cap = 400, 225, 14, 30
    sheet = Image.new("RGB", (4 * tw + 5 * pad, 4 * (th + cap) + 5 * pad), "#101116")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 20)
    for i, (stem, im) in enumerate(thumbs):
        x = pad + (i % 4) * (tw + pad)
        y = pad + (i // 4) * (th + cap + pad)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        draw.text((x, y + th + 5), f"{stem[:3].upper()}  {LABELS[stem[:3]]}", fill="#F1E9DB", font=font)
    sheet.save(HERE / "stage3-sheet.jpg", quality=85)
    print("sheet ->", HERE / "stage3-sheet.jpg")


if __name__ == "__main__":
    main(sys.argv[1])
