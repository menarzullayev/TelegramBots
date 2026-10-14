"""Vectorize the ChatGPT raven mark (1C) into a clean 4-color SVG.

1. Snap every pixel to the nearest brand color (white, raven black, scarf red, gold).
2. Flood-fill the outer white from the borders -> transparent; white left inside the
   silhouette (eye highlight, brow streak) becomes ivory so it survives on dark backgrounds.
3. Trace with vtracer.

Usage: python vectorize_mark.py <in.png> <out.svg>
"""
from __future__ import annotations

import sys
from collections import deque

import vtracer
from PIL import Image

BRAND = {
    "black": (16, 17, 22),
    "red": (200, 61, 70),
    "gold": (197, 161, 90),
    "white": (255, 255, 255),
}
IVORY = (241, 233, 219)


def nearest(rgb):
    return min(BRAND.values(), key=lambda c: sum((a - b) ** 2 for a, b in zip(rgb, c)))


def main(src: str, dst: str) -> None:
    img = Image.open(src).convert("RGB")
    img = img.resize((1024, 1024), Image.LANCZOS)
    w, h = img.size
    px = img.load()
    snapped = [[nearest(px[x, y]) for x in range(w)] for y in range(h)]

    white = BRAND["white"]
    outside = [[False] * w for _ in range(h)]
    queue = deque((x, y) for x in range(w) for y in (0, h - 1))
    queue.extend((x, y) for y in range(h) for x in (0, w - 1))
    while queue:
        x, y = queue.popleft()
        if not (0 <= x < w and 0 <= y < h) or outside[y][x] or snapped[y][x] != white:
            continue
        outside[y][x] = True
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    out = Image.new("RGBA", (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            c = snapped[y][x]
            if outside[y][x]:
                op[x, y] = (0, 0, 0, 0)
            else:
                op[x, y] = (*(IVORY if c == white else c), 255)
    clean = dst.replace(".svg", "-clean.png")
    out.save(clean)

    vtracer.convert_image_to_svg_py(
        clean,
        dst,
        colormode="color",
        hierarchical="stacked",
        mode="spline",
        filter_speckle=12,
        color_precision=6,
        layer_difference=24,
        corner_threshold=60,
        length_threshold=6.0,
        splice_threshold=45,
        path_precision=2,
    )
    print("wrote", dst, "and", clean)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
