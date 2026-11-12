"""Browser-free guards behind scripts/miniapp_matrix.py: locale keys, no <select>, no external font host, font coverage."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tezmafia.webapp.server import THEMES

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "tezmafia" / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
LOCALES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "tezmafia" / "locales").glob("*.json")}
FONTS = ROOT / "assets" / "fonts"
# Letters that Kazakh, Kyrgyz and Tajik (and Ukrainian) text needs beyond basic Russian Cyrillic.
CYR_EXT = "әғқңөұүһіҷҳӣӯӘҒҚҢӨҰҮҺІҶҲӢӮ"

FACE = re.compile(r"@font-face\{(.*?)\}", re.S)


def parse_faces(css: str) -> list[dict]:
    faces = []
    for body in FACE.findall(css):
        fam = re.search(r'font-family:"([^"]+)"', body)
        url = re.search(r"url\(/assets/fonts/([^)]+)\)", body)
        rng = re.search(r"unicode-range:([^;}]+)", body)
        assert fam and url and rng, body
        spans = []
        for part in rng.group(1).split(","):
            lo, _, hi = part.strip()[2:].partition("-")
            spans.append((int(lo, 16), int(hi or lo, 16)))
        faces.append({"family": fam.group(1), "file": url.group(1), "spans": spans})
    return faces


def uncovered(faces: list[dict], families: set[str], chars: str) -> str:
    """Characters that no face of the given families declares in its unicode-range."""
    return "".join(
        ch for ch in chars
        if not any(f["family"] in families and any(lo <= ord(ch) <= hi for lo, hi in f["spans"]) for f in faces)
    )


def theme_families() -> dict[str, set[str]]:
    """Custom (self-hosted) families each theme can reach through its --serif/--head/--type stacks and explicit font-family."""
    declared = {f["family"] for f in parse_faces(HTML)}

    def stacks(block: str) -> set[str]:
        names: set[str] = set()
        for m in re.finditer(r"(?:--serif|--head|--type|font-family)\s*:\s*([^;]+);", block):
            names |= {n.strip().strip("\"'") for n in m.group(1).split(",")} & declared
        return names

    base = HTML[HTML.index(":root {"):HTML.index(':root[data-theme="neon"]')]
    out = {}
    for theme in THEMES:
        m = re.search(rf':root\[data-theme="{theme}"\]\s*\{{(.*?)\n  \}}', HTML, re.S)
        block = m.group(1) if m else ""
        explicit = " ".join(re.findall(rf':root\[data-theme="{theme}"\][^{{]*\{{([^}}]*)\}}', HTML))
        out[theme] = stacks(block) | stacks(explicit) | (stacks(base) if not re.search(r"--(serif|type)", block) else set())
        if theme == "dossier":
            out[theme] = stacks(base) | stacks(explicit)
        elif "--type" not in block or "--serif" not in block:
            out[theme] |= stacks(base)
    return out


def test_every_locale_has_every_key_the_page_and_state_use() -> None:
    keys = set(re.findall(r'S\.strings\["([a-z_.]+)"\]', HTML))
    keys |= set(re.findall(r'\["[a-z]+", "([a-z]+\.[a-z_]+)"\]', HTML))
    keys |= {"lang.title", "app.close", "app.case", "theme.title", "theme.hint"} | {f"theme.{t}" for t in THEMES}
    assert len(keys) >= 20
    for code, data in LOCALES.items():
        missing = sorted(k for k in keys if k not in data)
        assert not missing, f"{code}: {missing}"


def test_all_eleven_locales_exist() -> None:
    assert set(LOCALES) == {"uz", "en", "ru", "az", "br", "id", "kg", "kz", "tj", "tr", "ua"}


def test_page_has_no_native_select_and_no_external_font_host() -> None:
    assert "<select" not in HTML.lower()
    for host in ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net", "cdnjs.cloudflare.com"):
        assert host not in HTML
    assert not re.search(r"@import\s+url|<link[^>]+stylesheet", HTML)


def test_every_font_face_file_exists_and_is_woff2() -> None:
    faces = parse_faces(HTML)
    assert faces
    for f in faces:
        path = FONTS / f["file"]
        assert path.is_file(), f["file"]
        assert path.read_bytes()[:4] == b"wOF2", f["file"]


def test_every_theme_stack_covers_the_cyrillic_extension_letters() -> None:
    faces = parse_faces(HTML)
    fams = theme_families()
    assert set(fams) == set(THEMES)
    for theme, families in fams.items():
        assert families, theme
        assert uncovered(faces, families, CYR_EXT) == "", f"{theme}: {uncovered(faces, families, CYR_EXT)}"


def test_the_primary_families_of_themes_without_cyrillic_ext_have_a_complete_fallback() -> None:
    """Jost and Poiret One ship no cyrillic-ext subset: deco must chain to a family that does (Inter)."""
    faces = parse_faces(HTML)
    assert uncovered(faces, {"Jost", "Poiret One"}, CYR_EXT) != ""
    assert uncovered(faces, {"Jost", "Poiret One", "Inter"}, CYR_EXT) == ""
    assert "Inter" in theme_families()["deco"]


def test_coverage_check_catches_a_missing_subset() -> None:
    """Negative: dropping every cyrillic-ext face must make the check report Kazakh/Tajik letters."""
    faces = [f for f in parse_faces(HTML) if "cyrillic-ext" not in f["file"]]
    for theme, families in theme_families().items():
        bad = uncovered(faces, families, CYR_EXT)
        assert "ә" in bad and "ҷ" in bad, theme
    assert uncovered(parse_faces("@font-face{font-family:\"X\";src:url(/assets/fonts/x.woff2);unicode-range:U+0400-045F}"), {"X"}, "ә") == "ә"
