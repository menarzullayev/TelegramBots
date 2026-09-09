"""Renders Claude's markdown+LaTeX solution text to a PNG image.

Uses matplotlib with usetex=True (real LaTeX via dvipng) for perfect math.
Falls back to Pillow plain-text if LaTeX compilation fails.
"""

import io
import logging
import re
import subprocess
import tempfile
import textwrap

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────
_BLOCK_MATH_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"\$(.+?)\$", re.DOTALL)
_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")
_ITALIC_RE = re.compile(r"\*(.*?)\*")
_HEADER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_HR_RE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\|[-| :]+\|$")
_TEXT_BRACED_RE = re.compile(r"\\text\{[^}]*\}")

# LaTeX commands that signal math content
_MATH_CMDS_RE = re.compile(
    r"\\(?:frac|dfrac|partial|Delta|delta|Rightarrow|Leftarrow|rightarrow|leftarrow|"
    r"cdot|left|right|approx|sqrt|sum|int|oint|iint|iiint|lim|sup|inf|"
    r"quad|qquad|vec|nabla|infty|times|div|pm|mp|leq|geq|neq|equiv|sim|"
    r"alpha|beta|gamma|epsilon|theta|lambda|mu|nu|pi|sigma|tau|phi|psi|omega|"
    r"Omega|Sigma|Pi|Theta|Phi|Psi|Lambda|Gamma|"
    r"min|max|sin|cos|tan|log|ln|exp|"
    r"begin|end|boxed)\b"
)

# Prose detection
_PROSE_RE = re.compile(r"\b[a-zA-ZА-Яа-яЎўҚқҒғҲҳ']{5,}\b")
_LATEX_WORDS = frozenset(
    {
        "frac",
        "dfrac",
        "partial",
        "delta",
        "Delta",
        "rightarrow",
        "Rightarrow",
        "leftarrow",
        "Leftarrow",
        "left",
        "right",
        "cdot",
        "boxed",
        "approx",
        "sqrt",
        "sum",
        "int",
        "oint",
        "iint",
        "iiint",
        "lim",
        "sup",
        "inf",
        "quad",
        "qquad",
        "text",
        "vec",
        "nabla",
        "infty",
        "times",
        "begin",
        "cases",
        "align",
        "matrix",
        "end",
        "sigma",
        "theta",
        "alpha",
        "beta",
        "gamma",
        "lambda",
        "omega",
        "Omega",
        "Sigma",
        "leq",
        "geq",
        "neq",
        "equiv",
        "mathrm",
        "mathbf",
        "overline",
        "hat",
        "tilde",
        "max",
        "min",
        "sin",
        "cos",
        "tan",
        "log",
        "exp",
        "pm",
        "mp",
        "cdots",
        "ldots",
        "vdots",
        "ddots",
        "forall",
        "exists",
        "subset",
    }
)

_STRONG_MATH = frozenset(
    {"frac", "dfrac", "partial", "Delta", "delta", "Rightarrow", "cdot", "sqrt", "sum", "int", "oint"}
)

_LATEX_UNICODE = {
    r"\Delta": "Δ",
    r"\delta": "δ",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\Gamma": "Γ",
    r"\epsilon": "ε",
    r"\varepsilon": "ε",
    r"\theta": "θ",
    r"\Theta": "Θ",
    r"\lambda": "λ",
    r"\Lambda": "Λ",
    r"\mu": "μ",
    r"\nu": "ν",
    r"\pi": "π",
    r"\Pi": "Π",
    r"\sigma": "σ",
    r"\Sigma": "Σ",
    r"\tau": "τ",
    r"\phi": "φ",
    r"\Phi": "Φ",
    r"\psi": "ψ",
    r"\Psi": "Ψ",
    r"\omega": "ω",
    r"\Omega": "Ω",
    r"\pm": "±",
    r"\mp": "∓",
    r"\times": "×",
    r"\div": "÷",
    r"\cdot": "·",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\neq": "≠",
    r"\approx": "≈",
    r"\equiv": "≡",
    r"\infty": "∞",
    r"\Rightarrow": "⇒",
    r"\rightarrow": "→",
    r"\Leftarrow": "⇐",
    r"\leftarrow": "←",
    r"\nabla": "∇",
    r"\forall": "∀",
    r"\exists": "∃",
    r"\sqrt": "√",
    r"\partial": "∂",
    r"\sum": "Σ",
    r"\prod": "Π",
    r"\int": "∫",
    r"\oint": "∮",
}

WRAP_WIDTH = 80
FIG_W = 12
DPI = 150


# ── Helpers ───────────────────────────────────────────────────────────────


def _is_bare_equation(line: str) -> bool:
    """True when line is a LaTeX equation not wrapped in $-delimiters."""
    s = line.strip()
    if not s or "$" in s:
        return False
    if not _MATH_CMDS_RE.search(s):
        return False
    if s.startswith("\\begin{"):
        return True
    cmds = _MATH_CMDS_RE.findall(s)
    prose_area = _TEXT_BRACED_RE.sub("", s)
    prose = [w for w in _PROSE_RE.findall(prose_area) if w.lower() not in _LATEX_WORDS]
    if s.startswith("\\"):
        return len(prose) == 0
    if re.match(r"^[=≈≤≥<>]\s*\\", s):
        return True
    has_strong = any(c[1:] in _STRONG_MATH for c in cmds)
    if has_strong and len(prose) <= 1:
        return True
    return False


def _degrade_to_text(expr: str) -> str:
    """Convert LaTeX expression to readable unicode text."""
    s = expr
    s = re.sub(r"\\begin\{[^}]*\}", "", s)
    s = re.sub(r"\\end\{[^}]*\}", "", s)
    s = s.replace("\\\\", "  |  ")
    s = re.sub(r"\\boxed\{((?:[^{}]|\{[^{}]*\})*)\}", r"[ \1 ]", s)
    for _ in range(4):
        s = re.sub(r"\\(?:frac|dfrac)\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", s)
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    for cmd, uni in _LATEX_UNICODE.items():
        s = s.replace(cmd, uni)
    s = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = re.sub(r"\\[!,;.]", "", s)
    s = re.sub(r"[{}]", " ", s)
    return " ".join(s.split())


def _wrap_text_line(line: str) -> list[str]:
    if len(line) <= WRAP_WIDTH:
        return [line]
    if "$" in line:
        return [line]
    try:
        return textwrap.wrap(line, width=WRAP_WIDTH, break_long_words=True) or [line]
    except Exception:
        return [line]


def _strip_markdown(text: str) -> str:
    text = _HEADER_RE.sub("▶ ", text)
    text = _BOLD_RE.sub(r"\1", text)
    text = _ITALIC_RE.sub(r"\1", text)
    text = _HR_RE.sub("", text)
    return text


def _preprocess(text: str) -> str:
    """Clean markdown and wrap bare LaTeX equation lines in $$...$$."""
    text = _strip_markdown(text)
    lines = text.split("\n")
    result: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if _TABLE_SEP_RE.match(stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]:
            cols = [c.strip() for c in stripped[1:-1].split("|")]
            result.append("  ".join(cols))
            continue
        if _is_bare_equation(stripped):
            result.append(f"$${stripped}$$")
            continue
        result.append(raw)
    return "\n".join(result)


def _build_items(text: str) -> list[tuple[str, str]]:
    """Split preprocessed text into ('text'|'block_math'|'empty', content) items."""
    items: list[tuple[str, str]] = []
    last = 0

    for m in _BLOCK_MATH_RE.finditer(text):
        for raw_line in text[last : m.start()].split("\n"):
            s = raw_line.strip()
            if not s:
                items.append(("empty", ""))
            else:
                for wl in _wrap_text_line(s):
                    items.append(("text", wl))
        items.append(("block_math", m.group(1).strip()))
        last = m.end()

    for raw_line in text[last:].split("\n"):
        s = raw_line.strip()
        if not s:
            items.append(("empty", ""))
        else:
            for wl in _wrap_text_line(s):
                items.append(("text", wl))

    merged: list[tuple[str, str]] = []
    for item in items:
        if item[0] == "empty" and merged and merged[-1][0] == "empty":
            continue
        merged.append(item)
    while merged and merged[0][0] == "empty":
        merged.pop(0)
    while merged and merged[-1][0] == "empty":
        merged.pop()
    return merged


# ── LaTeX document builder ────────────────────────────────────────────────


def _build_latex_doc(items: list[tuple[str, str]]) -> str:
    """Build a full LaTeX document from render items."""
    lines = [
        r"\documentclass[12pt]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{amsmath,amssymb,amsthm}",
        r"\usepackage[margin=1.5cm,top=1cm,bottom=1cm]{geometry}",
        r"\usepackage{parskip}",
        r"\pagestyle{empty}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{4pt}",
        r"\begin{document}",
    ]

    for kind, val in items:
        if kind == "empty":
            lines.append("")  # blank line = paragraph break in LaTeX
        elif kind == "block_math":
            lines.append(r"\[" + "\n" + val + "\n" + r"\]")
            lines.append("")
        else:
            escaped = _escape_text_for_latex(val)
            lines.append(escaped + r"\\")  # force line break after each text item

    lines.append(r"\end{document}")
    return "\n".join(lines)


_LATEX_SPECIAL = str.maketrans(
    {
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "^": r"\^{}",
        "~": r"\textasciitilde{}",
        "▶": r"$\blacktriangleright$",
        "□": r"$\square$",
    }
)


def _escape_text_for_latex(text: str) -> str:
    """Escape LaTeX special chars in plain-text segments, keeping $...$ intact."""
    parts = re.split(r"(\$[^$]+\$)", text)
    result = []
    for part in parts:
        if part.startswith("$") and part.endswith("$"):
            result.append(part)  # math: leave as-is
        else:
            result.append(part.translate(_LATEX_SPECIAL))
    return "".join(result)


# ── Renderers ─────────────────────────────────────────────────────────────


def _render_with_latex(latex_doc: str) -> bytes:
    """Compile LaTeX doc → DVI → PNG via dvipng."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = f"{tmpdir}/solution.tex"
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_doc)

        result = subprocess.run(
            ["latex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        import os

        dvi_path = f"{tmpdir}/solution.dvi"
        if not os.path.exists(dvi_path):
            raise RuntimeError(f"latex failed (no DVI):\n{result.stdout[-800:]}")

        png_path = f"{tmpdir}/solution.png"
        dvipng_result = subprocess.run(
            [
                "dvipng",
                "-D",
                str(DPI * 2),  # 2× for sharpness
                "-T",
                "tight",
                "-bg",
                "White",
                "-fg",
                "Black",
                "-o",
                png_path,
                dvi_path,
            ],
            capture_output=True,
            timeout=15,
        )
        if dvipng_result.returncode != 0:
            raise RuntimeError(f"dvipng failed: {dvipng_result.stderr.decode()[:300]}")

        # dvipng produces solution1.png (one page)
        import glob

        pages = sorted(glob.glob(f"{tmpdir}/solution*.png"))
        if not pages:
            raise RuntimeError("dvipng produced no PNG files")

        # If multiple pages, stack vertically
        if len(pages) == 1:
            return open(pages[0], "rb").read()

        from PIL import Image as PILImage

        imgs = [PILImage.open(p) for p in pages]
        total_h = sum(i.height for i in imgs)
        max_w = max(i.width for i in imgs)
        combined = PILImage.new("RGB", (max_w, total_h), "white")
        y_off = 0
        for img in imgs:
            combined.paste(img, (0, y_off))
            y_off += img.height
        buf = io.BytesIO()
        combined.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()


def _render_pillow_fallback(solution_text: str) -> bytes:
    """Last-resort: Pillow plain-text render with unicode math symbols."""
    from PIL import Image, ImageDraw, ImageFont

    text = _preprocess(solution_text)
    text = _BLOCK_MATH_RE.sub(lambda m: "\n" + _degrade_to_text(m.group(1)) + "\n", text)
    text = _INLINE_MATH_RE.sub(r"\1", text)

    raw_lines: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        raw_lines.append("") if not s else raw_lines.extend(_wrap_text_line(s))

    lines: list[str] = []
    for ln in raw_lines:
        if not ln and lines and not lines[-1]:
            continue
        lines.append(ln)
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    font_size, line_h_px, padding, width = 20, 32, 40, 1400
    height = max(200, len(lines) * line_h_px + 2 * padding)
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ):
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            continue

    y = padding
    for line in lines:
        draw.text((padding, y), line, fill="#1a1a2e", font=font)
        y += line_h_px

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ── Public API ────────────────────────────────────────────────────────────


def render_solution_to_png(solution_text: str) -> bytes | None:
    """Return PNG bytes, or None if all rendering fails."""
    text = _preprocess(solution_text)
    items = _build_items(text)

    if not items:
        return None

    try:
        latex_doc = _build_latex_doc(items)
        return _render_with_latex(latex_doc)
    except Exception as e:
        logger.warning("LaTeX render failed (%s), using Pillow fallback", e)

    try:
        return _render_pillow_fallback(solution_text)
    except Exception as e:
        logger.error("All render methods failed: %s", e)
        return None
