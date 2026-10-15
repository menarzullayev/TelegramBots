"""Render a branded chat mock-up (a "screenshot" of a TezMafia conversation) for channel posts.

    python -m scripts.channel_mock channel/posts/04-first-game.json out.jpg

Input is a post's `visual.mock`: {"chat": "group"|"bot", "messages": [{"from", "name", "text", "buttons"}]}.
Telegram-like layout in the Raven palette: header with the chat avatar, left bubbles for the bot and other
players, right bubbles for "you", inline buttons under bot messages. Fictional names only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tezmafia.brand import ASSETS, PALETTE
from tezmafia.cards import FONTS_BOLD, FONTS_REGULAR, _font, _rgb

EMOJI_FONTS = ("C:/Windows/Fonts/seguiemj.ttf", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")
W = 1080
PAD = 40
BUBBLE_MAX = 720
LINE = 1.32


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2190 <= o <= 0x2BFF or o in (0x200D, 0xFE0F, 0x20E3)


def _runs(text: str) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    for ch in text:
        e = _is_emoji(ch)
        if out and out[-1][0] == e:
            out[-1] = (e, out[-1][1] + ch)
        else:
            out.append((e, ch))
    return out


_EMOJI: dict[int, object] = {}


def _emoji_font(size: int):
    if size not in _EMOJI:
        path = next((f for f in EMOJI_FONTS if Path(f).is_file()), None)
        _EMOJI[size] = ImageFont.truetype(path, int(size * 0.9)) if path else None
    return _EMOJI[size]


def _length(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    ef = _emoji_font(font.size) if hasattr(font, "size") else None
    return sum(draw.textlength(t, font=ef if (e and ef) else font) for e, t in _runs(text))


def _text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, fill) -> None:
    """Text with colour emoji: emoji runs use the system emoji font, the rest the brand font."""
    x, y = xy
    ef = _emoji_font(font.size) if hasattr(font, "size") else None
    for e, t in _runs(text):
        if e and ef:
            # align baselines: the emoji font has a different ascent than the text font
            dy = font.getmetrics()[0] - ef.getmetrics()[0]
            draw.text((x, y + dy), t, font=ef, embedded_color=True)
            x += draw.textlength(t, font=ef)
        else:
            draw.text((x, y), t, font=font, fill=fill)
            x += draw.textlength(t, font=font)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if _length(draw, trial, font) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _avatar(size: int) -> Image.Image:
    img = Image.open(ASSETS / "raven" / "avatar.jpg").convert("RGB").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def render(mock: dict) -> Image.Image:
    bg, card, ivory, gold, ash, burgundy = (_rgb(PALETTE[k]) for k in
                                            ("raven_black", "charcoal", "ivory", "gold", "ash", "burgundy"))
    body = _font(FONTS_REGULAR, 34)
    bold = _font(FONTS_BOLD, 30)
    small = _font(FONTS_REGULAR, 26)
    button_font = _font(FONTS_BOLD, 30)
    scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    title = "TezMafia" if mock.get("chat") == "bot" else mock.get("title", "Qorashahar · guruh")

    # measure
    layout = []
    y = 150
    for m in mock.get("messages", []):
        mine = m.get("from") == "user" and m.get("mine", m.get("name") in (None, "", "Siz"))
        name = None if mine else (m.get("name") or ("TezMafia" if m.get("from") == "bot" else "O‘yinchi"))
        lines = _wrap(scratch, m.get("text", ""), body, BUBBLE_MAX - 2 * 28)
        text_h = int(len(lines) * 34 * LINE)
        h = 24 + (40 if name else 0) + text_h + 20
        rows = m.get("buttons") or []
        btn_h = len(rows) * 78
        layout.append((m, mine, name, lines, h, rows, y))
        y += h + (btn_h + 8 if rows else 0) + 22
    height = max(y + 40, 600)

    img = Image.new("RGB", (W, height), bg)
    d = ImageDraw.Draw(img)
    # subtle header
    d.rectangle((0, 0, W, 120), fill=card)
    img.paste(_avatar(80), (PAD, 20), _avatar(80))
    d.text((PAD + 100, 28), title, font=_font(FONTS_BOLD, 36), fill=ivory)
    d.text((PAD + 100, 74), "bot" if mock.get("chat") == "bot" else "a‘zolar · onlayn", font=small, fill=ash)
    d.line((0, 120, W, 120), fill=burgundy, width=3)

    for m, mine, name, lines, h, rows, top in layout:
        width = min(BUBBLE_MAX, max(int(max((_length(scratch, x, body) for x in lines), default=200)) + 56,
                                    int(scratch.textlength(name or "", font=bold)) + 56, 260))
        if rows:
            width = BUBBLE_MAX
        x0 = W - PAD - width if mine else PAD
        fill = (58, 30, 40) if mine else card
        d.rounded_rectangle((x0, top, x0 + width, top + h), radius=26, fill=fill)
        ty = top + 22
        if name:
            d.text((x0 + 28, ty), name, font=bold, fill=gold if m.get("from") == "bot" else _rgb(PALETTE["red_text"]))
            ty += 40
        for line in lines:
            _text(d, (x0 + 28, ty), line, body, ivory)
            ty += int(34 * LINE)
        by = top + h + 8
        for row in rows:
            n = max(1, len(row))
            gap = 10
            bw = (width - gap * (n - 1)) // n
            for i, label in enumerate(row):
                bx = x0 + i * (bw + gap)
                d.rounded_rectangle((bx, by, bx + bw, by + 68), radius=18, fill=(36, 38, 48))
                tw = _length(d, label, button_font)
                while tw > bw - 24 and len(label) > 4:
                    label = label[:-2] + "…"
                    tw = _length(d, label, button_font)
                _text(d, (bx + (bw - tw) / 2, by + 16), label, button_font, ivory)
            by += 78
    d.text((W - PAD - d.textlength("TEZMAFIA", font=small), height - 36), "TEZMAFIA", font=small, fill=ash)
    return img


def main() -> None:
    post = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    render(post["visual"]["mock"]).save(sys.argv[2], "JPEG", quality=88, optimize=True)


if __name__ == "__main__":
    main()
