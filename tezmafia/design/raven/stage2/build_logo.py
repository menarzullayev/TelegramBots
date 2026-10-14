"""Build the TezMafia logo lockups: raven mark + outlined Bahnschrift wordmark.

The wordmark is converted to SVG paths (no font dependency at render time).
Writes 4 transparent SVGs: horizontal/stacked x light/dark backgrounds.

Usage: python build_logo.py <mark.svg> <mark-on-dark.svg> <out_dir>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

FONT = r"C:\Windows\Fonts\bahnschrift.ttf"
AXES = {"wght": 600, "wdth": 87.5}
TRACKING = 0.06  # em, matches the approved preview
COLORS = {
    "dark": {"tez": "#F1E9DB", "mafia": "#C83D46"},
    "light": {"tez": "#101116", "mafia": "#C83D46"},
}


def load_font() -> TTFont:
    return instantiateVariableFont(TTFont(FONT), AXES, inplace=False)


def word_paths(font: TTFont, parts: list[tuple[str, str]], size: float, x0: float, baseline: float):
    """Return (svg <path> elements, advance width) for colored text runs."""
    upm = font["head"].unitsPerEm
    scale = size / upm
    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    hmtx = font["hmtx"]
    out, x = [], x0
    for text, color in parts:
        d = []
        for ch in text:
            name = cmap[ord(ch)]
            pen = SVGPathPen(glyphs)
            glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
            d.append(pen.getCommands())
            x += hmtx[name][0] * scale + TRACKING * size
        out.append(f'<path fill="{color}" d="{" ".join(d)}"/>')
    return "".join(out), x - x0 - TRACKING * size


def mark_inner(svg_path: str) -> str:
    raw = Path(svg_path).read_text(encoding="utf-8")
    return re.search(r"<svg[^>]*>(.*)</svg>", raw, re.S).group(1)


def main(mark: str, mark_dark: str, out_dir: str) -> None:
    font = load_font()
    upm = font["head"].unitsPerEm
    cap = font["OS/2"].sCapHeight / upm
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for theme, colors in COLORS.items():
        inner = mark_inner(mark_dark if theme == "dark" else mark)
        parts = [("TEZ", colors["tez"]), ("MAFIA", colors["mafia"])]

        # Horizontal: mark 260px tall, cap height = 46% of it.
        h, m = 300, 260
        size = (m * 0.46) / cap
        text_x = 20 + m + 36
        baseline = h / 2 + (cap * size) / 2
        paths, width = word_paths(font, parts, size, text_x, baseline)
        w = round(text_x + width + 24)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
               f'<svg x="20" y="20" width="{m}" height="{m}" viewBox="0 0 1024 1024">{inner}</svg>{paths}</svg>\n')
        (out / f"logo-horizontal-{theme}.svg").write_text(svg, encoding="utf-8")

        # Stacked: mark on top, wordmark centered below.
        m2 = 320
        size2 = (m2 * 0.30) / cap
        _, width2 = word_paths(font, parts, size2, 0, 0)
        w2 = round(max(m2, width2) + 60)
        base2 = 30 + m2 + 24 + cap * size2
        paths2, _ = word_paths(font, parts, size2, (w2 - width2) / 2, base2)
        h2 = round(base2 + 36)
        svg2 = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w2}" height="{h2}" viewBox="0 0 {w2} {h2}">'
                f'<svg x="{(w2 - m2) / 2}" y="30" width="{m2}" height="{m2}" viewBox="0 0 1024 1024">{inner}</svg>{paths2}</svg>\n')
        (out / f"logo-stacked-{theme}.svg").write_text(svg2, encoding="utf-8")
    print("logos ->", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
