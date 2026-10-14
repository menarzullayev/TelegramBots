"""Name, square-crop and export the 21 stage-4 role cards as 640x640 JPGs, plus a review sheet.

Downloads are matched to roles by download order (the Role enum order in tezmafia/roles.py).

Usage: python finalize.py <downloads_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
LOCALE = HERE.parents[2] / "tezmafia" / "locales" / "uz.json"
ROLES = [  # (download file, role id) in generation order
    ("Raven Guardian with a Golden Lantern.png", "citizen"),
    ("Raven Assassin Presents a Sealed Secret.png", "mafia"),
    ("Raven Don on a Crimson Throne.png", "don"),
    ("Raven Detective with Magnifying Glass.png", "detective"),
    ("Raven Inspector Taking Notes.png", "sergeant"),
    ("Raven Alchemist with Glowing Green Elixir.png", "doctor"),
    ("Crimson-Hooded Raven Warden.png", "maniac"),
    ("Raven Noble with a Crimson Rose.png", "hooker"),
    ("Crimson Raven Detective with Sealed Briefcase.png", "lawyer"),
    ("Raven Masquerade in Purple and Gold.png", "suicide"),
    ("Raven Pilgrim Under Golden Light.png", "hobo"),
    ("Golden Coin Raven Rogue.png", "lucky"),
    ("Raven Warrior and Ember Orb.png", "kamikaze"),
    ("Raven Magistrate with a Golden Key.png", "mayor"),
    ("Raven Spy Behind the Velvet Curtain.png", "journalist"),
    ("Raven Assassin Beneath the Crimson Hood.png", "killer"),
    ("The Raven\u2019s Crimson and Azure Masquerade.png", "werewolf"),
    ("Emberlit Raven with Crimson Medallion.png", "arsonist"),
    ("Raven Mage and Golden Arcana.png", "mage"),
    ("Golden-Eyed Raven Trickster.png", "crook"),
    ("Raven Detective with Golden Magnifying Glass.png", "snitch"),
]


def to_square(im: Image.Image, size: int = 640) -> Image.Image:
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return im.resize((size, size), Image.LANCZOS)


def main(downloads: str) -> None:
    dl = Path(downloads)
    names = json.loads(LOCALE.read_text(encoding="utf-8"))
    out = HERE / "final"
    out.mkdir(exist_ok=True)
    thumbs = []
    for i, (src, role) in enumerate(ROLES, 1):
        raw = Image.open(dl / src)
        stem = f"r{i:02d}-{role}"
        raw.save(HERE / f"{stem}.png")
        im = to_square(raw.convert("RGB"))
        im.save(out / f"{role}.jpg", quality=88, optimize=True, progressive=True)
        thumbs.append((stem, names[f"role.{role}"], im))
        print(f"{stem}: {raw.size} -> 640x640")

    cols, tw, pad, cap = 7, 240, 12, 30
    rows = -(-len(thumbs) // cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad, rows * (tw + cap) + (rows + 1) * pad), "#101116")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 18)
    for i, (stem, label, im) in enumerate(thumbs):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (tw + cap + pad)
        sheet.paste(im.resize((tw, tw), Image.LANCZOS), (x, y))
        draw.text((x, y + tw + 5), f"{stem[:3].upper()}  {label}", fill="#F1E9DB", font=font)
    sheet.save(HERE / "stage4-sheet.jpg", quality=85)
    print("sheet ->", HERE / "stage4-sheet.jpg")


if __name__ == "__main__":
    main(sys.argv[1])
