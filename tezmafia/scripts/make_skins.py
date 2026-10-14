"""Render the role-card skins (DECISION-17) from the Raven portraits: noir, gold, neon.

    python -m scripts.make_skins            # writes assets/raven/skins/<style>/<role>.jpg

Deterministic (no randomness), so re-running only changes files when the portraits change.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from tezmafia.brand import ASSETS

STYLES = ("noir", "gold", "neon")
SRC = ASSETS / "raven" / "roles"
OUT = ASSETS / "raven" / "skins"


def _vignette(size: tuple[int, int], strength: float) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((-w * 0.15, -h * 0.15, w * 1.15, h * 1.15), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w * 0.12))
    return ImageOps.invert(mask).point(lambda v: int(v * strength))


def noir(img: Image.Image) -> Image.Image:
    g = ImageEnhance.Contrast(ImageOps.grayscale(img)).enhance(1.55)
    g = ImageOps.autocontrast(g, cutoff=1)
    out = Image.merge("RGB", (g, g, g))
    shade = Image.new("RGB", img.size, (0, 0, 0))
    out = Image.composite(shade, out, _vignette(img.size, 0.75))
    d = ImageDraw.Draw(out)
    w, h = img.size
    d.rectangle((10, 10, w - 11, h - 11), outline=(235, 235, 235), width=3)
    return out


def gold(img: Image.Image) -> Image.Image:
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=1).point(lambda v: int(255 * (v / 255) ** 0.72))  # lift the dark portraits
    toned = ImageOps.colorize(g, black=(34, 22, 6), mid=(204, 150, 58), white=(255, 242, 196))
    out = ImageEnhance.Contrast(toned).enhance(1.1)
    w, h = img.size
    d = ImageDraw.Draw(out)
    for i, col in enumerate(((120, 84, 24), (232, 190, 92), (255, 233, 160), (176, 128, 40))):
        d.rectangle((6 + i * 4, 6 + i * 4, w - 7 - i * 4, h - 7 - i * 4), outline=col, width=4)
    for x, y in ((24, 24), (w - 25, 24), (24, h - 25), (w - 25, h - 25)):  # corner studs
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 226, 140), outline=(120, 84, 24), width=2)
    return out


def neon(img: Image.Image) -> Image.Image:
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=2)
    duo = ImageOps.colorize(g, black=(10, 4, 30), mid=(160, 30, 170), white=(90, 250, 255))
    edges = ImageOps.grayscale(img).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.2))
    edges = ImageOps.autocontrast(edges).point(lambda v: min(255, int(v * 1.6)))
    glow = Image.merge("RGB", (edges.point(lambda v: v // 3), edges, edges))
    out = ImageChops.screen(duo, glow)
    w, h = img.size
    frame = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(frame).rectangle((12, 12, w - 13, h - 13), outline=(255, 40, 200), width=5)
    out = ImageChops.screen(out, frame.filter(ImageFilter.GaussianBlur(4)))
    ImageDraw.Draw(out).rectangle((12, 12, w - 13, h - 13), outline=(255, 140, 235), width=2)
    return out


RENDER = {"noir": noir, "gold": gold, "neon": neon}


def main() -> None:
    roles = sorted(SRC.glob("*.jpg"))
    for style in STYLES:
        target = OUT / style
        target.mkdir(parents=True, exist_ok=True)
        for path in roles:
            img = Image.open(path).convert("RGB")
            RENDER[style](img).save(target / path.name, "JPEG", quality=86, optimize=True)
    # /skins preview: the Mafia card in the original and every style, side by side
    tiles = [Image.open(SRC / "mafia.jpg").convert("RGB")] + [Image.open(OUT / s / "mafia.jpg") for s in STYLES]
    side = 320
    sheet = Image.new("RGB", (side * len(tiles), side), (10, 10, 12))
    for i, tile in enumerate(tiles):
        sheet.paste(tile.resize((side, side), Image.LANCZOS), (i * side, 0))
    sheet.save(OUT / "preview.jpg", "JPEG", quality=86, optimize=True)
    print(f"{len(roles)} roles x {len(STYLES)} styles -> {OUT}")


if __name__ == "__main__":
    main()


__all__ = ["STYLES", "RENDER", "Path"]
