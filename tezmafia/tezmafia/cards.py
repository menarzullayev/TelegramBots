"""Shareable result card: the player's Raven role portrait plus name, role, result and level.

1280x720 JPEG (the scene format Telegram previews well). Fonts are looked up on the host (Windows
Segoe UI / Arial, Linux DejaVu) so Cyrillic and Uzbek Latin names render; Pillow's built-in font is
the last resort. No emoji in the image: system emoji fonts are not portable.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tezmafia.brand import ASSETS, PALETTE, role_card

W, H = 1280, 720
FONTS_BOLD = (
    "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)
FONTS_REGULAR = (
    "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


def _font(paths: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _fit(draw: ImageDraw.ImageDraw, text: str, paths: tuple[str, ...], size: int, max_w: int):
    """Largest font (down to 60% of `size`) that fits `max_w`; text is cut with an ellipsis if still too long."""
    for s in range(size, int(size * 0.6), -2):
        font = _font(paths, s)
        if draw.textlength(text, font=font) <= max_w:
            return text, font
    font = _font(paths, int(size * 0.6))
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…", font


def result_card(name: str, role: str, role_title: str, won: bool, result_line: str, footer: str) -> bytes:
    bg, ivory, gold, red, ash = (_rgb(PALETTE[k]) for k in ("raven_black", "ivory", "gold", "raven_red", "ash"))
    img = Image.new("RGB", (W, H), bg)
    path = role_card(role)
    if path and (ASSETS / path).is_file():
        portrait = Image.open(ASSETS / path).convert("RGB").resize((H, H), Image.LANCZOS)
        img.paste(portrait, (0, 0))
        # soft edge from the portrait into the dark panel
        fade = Image.linear_gradient("L").rotate(90).resize((160, H))
        img.paste(Image.new("RGB", (160, H), bg), (H - 160, 0), fade)
    draw = ImageDraw.Draw(img)
    x, max_w = H + 30, W - H - 70
    draw.text((x, 70), "TEZMAFIA", font=_font(FONTS_BOLD, 34), fill=gold)
    text, font = _fit(draw, name, FONTS_BOLD, 64, max_w)
    draw.text((x, 150), text, font=font, fill=ivory)
    text, font = _fit(draw, role_title, FONTS_REGULAR, 44, max_w)
    draw.text((x, 250), text, font=font, fill=gold)
    accent = gold if won else red
    draw.rounded_rectangle((x, 345, x + max_w, 445), radius=18, outline=accent, width=4)
    text, font = _fit(draw, result_line, FONTS_BOLD, 46, max_w - 40)
    draw.text((x + 22, 370), text, font=font, fill=accent)
    text, font = _fit(draw, footer, FONTS_REGULAR, 30, max_w)
    draw.text((x, 600), text, font=font, fill=ash)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()
