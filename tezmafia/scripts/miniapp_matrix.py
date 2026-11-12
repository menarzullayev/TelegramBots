"""Browser QA matrix for the TezMafia Mini App: every theme x language x tab x width, plus the language sheet.

Needs Playwright for Python (NOT a project dependency; install it into a separate venv) and a running preview:

    python -m scripts.webapp_preview                      # http://127.0.0.1:8797, supports ?lang=xx&theme=yy
    python scripts/miniapp_matrix.py --out DIR [--tag before] [--workers 5] [--themes dossier,neon] [--langs uz,ru]

Optional: fonttools + brotli (names the exact characters a theme's fonts lack), Pillow (contact sheets).
Per state it checks: horizontal overflow, text overflow/clipping, glyph fallback (Chrome's own "rendered fonts" via CDP),
console/page errors and failed requests, tap targets under 44x44, raw i18n keys and placeholders, WCAG AA contrast, and
strings identical to English. Writes report-<tag>.json, summary-<tag>.md and screenshots of failing states only.
"""

# ruff: noqa: B023  (the nested helpers only run inside the loop iteration that defines them)
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
THEMES = ["dossier", "neon", "deco", "day", "comic"]
LANGS = ["uz", "en", "ru", "az", "br", "id", "kg", "kz", "tj", "tr", "ua"]
TABS = ["dossier", "roles", "wanted", "log", "market"]
WIDTHS = [360, 390, 430]
HEIGHT = 780
SHEET_LANGS = ["uz", "ru", "kz"]
SHOT_CAP = 3  # screenshots kept per distinct issue signature, per worker
HTML_LANG = {"ua": "uk", "kz": "kk", "kg": "ky", "tj": "tg", "br": "pt-BR"}
# Seed data and brand names that are legitimately identical in every language.
SAME_OK = re.compile(r"^(TezMafia|Saidakbar|Nodir|Dilnoza|Aziz|Malika|Qora Qarg.a|[\W\d_]+)$")

PAGE_JS = r"""
async (opts) => {
  const SEL_TAP = 'button, a[href], [role=tab], [role=option], input, select, summary';
  const rootEl = document.querySelector(opts.root) || document.body;
  document.querySelectorAll('[data-mx],[data-mxc]').forEach(e => { e.removeAttribute('data-mx'); e.removeAttribute('data-mxc'); });
  await Promise.race([
    Promise.all([...document.images].filter(i => !i.complete && i.getBoundingClientRect().width > 0)
      .map(i => new Promise(r => { i.onload = i.onerror = r; }))),
    new Promise(r => setTimeout(r, 2500))]);
  await document.fonts.ready;
  const vw = document.documentElement.clientWidth;  // innerWidth grows with overflow under mobile emulation
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const parse = s => {
    if (cache.has(s)) return cache.get(s);
    let r = null;
    const m = /^rgba?\(([^)]+)\)$/.exec(s || '');
    if (m) {
      const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
      r = [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    } else if (!s || s === 'transparent') r = [0, 0, 0, 0];
    else {
      cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1);
      const d = cx.getImageData(0, 0, 1, 1).data; r = [d[0], d[1], d[2], d[3] / 255];
    }
    cache.set(s, r); return r;
  };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = c => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const over = (top, bot) => {
    const a = top[3];
    return [top[0] * a + bot[0] * (1 - a), top[1] * a + bot[1] * (1 - a), top[2] * a + bot[2] * (1 - a), 1];
  };
  const sel = e => {
    const part = n => n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') +
      [...n.classList].filter(c => !/^(on|hit|me|won|off)$/.test(c)).slice(0, 3).map(c => '.' + c).join('');
    const out = []; let n = e;
    for (let i = 0; i < 3 && n && n !== document.body; i++, n = n.parentElement) out.unshift(part(n));
    return out.join(' > ');
  };
  const out = { issues: [], texts: [], fonts: [], bad_faces: [] };
  const add = (cat, e, detail, extra = {}) => out.issues.push({ cat, sel: sel(e), detail, ...extra });
  const docW = document.documentElement.scrollWidth;
  if (docW > vw) out.issues.push({ cat: 'overflow_doc', sel: 'html', detail: `scrollWidth ${docW} > viewport ${vw}` });
  for (const f of document.fonts) if (f.status === 'error') out.bad_faces.push(f.family + ' ' + f.unicodeRange);
  const clipping = e => {
    for (let n = e.parentElement; n && n !== document.body && n !== document.documentElement; n = n.parentElement) {
      const o = getComputedStyle(n).overflowX;
      if (o !== 'visible') return true;
    }
    return false;
  };
  let idx = 0;
  for (const e of rootEl.querySelectorAll('*')) {
    if (e instanceof SVGElement && e.tagName !== 'svg') continue;
    if (e.closest('svg') && e.tagName !== 'svg') continue;
    if (e.closest('.sk, script, style, template')) continue;
    if (opts.exclude && e.closest(opts.exclude)) continue;
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    let opac = 1;
    for (let n = e; n; n = n.parentElement) opac *= parseFloat(getComputedStyle(n).opacity);
    if (opac < 0.05) continue;
    if ((r.right > vw + 0.5 || r.left < -0.5) && cs.position !== 'fixed' && !clipping(e))
      add('overflow_el', e, `box ${Math.round(r.left)}..${Math.round(r.right)} vs viewport 0..${vw}`);
    if (e.matches(SEL_TAP) && (r.width < 43.5 || r.height < 43.5))
      add('tap_target', e, `${Math.round(r.width)}x${Math.round(r.height)}`, { w: Math.round(r.width), h: Math.round(r.height) });
    const direct = [...e.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
    if (!direct) continue;
    if (cs.display !== 'inline') {
      const ox = e.scrollWidth - e.clientWidth, oy = e.scrollHeight - e.clientHeight;
      if (ox > 1 && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') {
        if (cs.overflowX === 'visible') add('text_overflow', e, `text ${e.scrollWidth}px in a ${e.clientWidth}px box`, { text: direct.slice(0, 60) });
        else add(cs.textOverflow === 'ellipsis' ? 'text_truncated' : 'text_clipped', e, `text ${e.scrollWidth}px in a ${e.clientWidth}px box`, { text: direct.slice(0, 60) });
      }
      if (oy > 1 && (cs.overflowY === 'hidden' || cs.overflowY === 'clip'))
        add('text_clipped', e, `text ${e.scrollHeight}px tall in a ${e.clientHeight}px box`, { text: direct.slice(0, 60) });
    }
    let shown = direct;
    if (cs.textTransform === 'uppercase') shown = direct.toLocaleUpperCase(document.documentElement.lang || 'en');
    else if (cs.textTransform === 'lowercase') shown = direct.toLocaleLowerCase(document.documentElement.lang || 'en');
    out.texts.push(direct);
    if (/\b(app|btn|theme|lang|top|chr|stars|skins|gems|quests?|profile|ach|q|cmd|recruiter|clan|tour)\.[a-z_][a-z_0-9.]*/.test(direct) && !/\d\.\d/.test(direct))
      add('raw_key', e, direct.slice(0, 80));
    if (/\{[a-z_0-9]+\}|%[sd]\b|\bundefined\b|\bNaN\b|\[object /.test(direct)) add('placeholder', e, direct.slice(0, 80));
    out.fonts.push({ i: idx++, shown, family: cs.fontFamily, weight: cs.fontWeight, sel: sel(e) });
    e.setAttribute('data-mx', String(idx - 1));
    // contrast: composite the backgrounds from the element up to the first opaque layer
    const layers = []; let imgs = false;
    for (let n = e; n; n = n.parentElement) {
      const ns = getComputedStyle(n), bg = parse(ns.backgroundColor);
      if (ns.backgroundImage !== 'none' && n !== document.documentElement) imgs = true;
      if (bg[3] > 0) layers.push(bg);
      if (bg[3] >= 1) break;
    }
    let base = [255, 255, 255, 1];
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    const fg = parse(cs.color);
    const a = fg[3] * opac;
    if (a < 0.05) continue;
    const mixed = over([fg[0], fg[1], fg[2], a], base);
    const L1 = lum(mixed), L2 = lum(base);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = (px >= 24 || (px >= 18.66 && bold)) ? 3 : 4.5;
    if (ratio < need) {
      const extra = { ratio: +ratio.toFixed(2), need, text: direct.slice(0, 40), approx: imgs };
      if (imgs) {  // gradients/images under the text: the DOM colours are a guess, so python re-measures real pixels
        e.setAttribute('data-mxc', String(out.issues.length));
        Object.assign(extra, { fg: [mixed[0], mixed[1], mixed[2]], a, rect: [r.left + scrollX, r.top + scrollY, r.width, r.height], mxc: out.issues.length });
      }
      add('contrast', e, `${ratio.toFixed(2)}:1 < ${need}:1`, extra);
    }
  }
  return out;
}
"""

# --selftest injects one deliberate defect per check and fails unless every check reports it (negative test).
SELFTEST_JS = r"""
() => {
  const host = document.querySelector('#dossier') || document.body;
  const add = (tag, css, text) => { const n = document.createElement(tag); n.style.cssText = css; if (text) n.textContent = text; host.append(n); return n; };
  add('div', 'position:absolute;top:0;left:0;width:640px;height:12px;background:#c00;pointer-events:none');
  add('p', 'width:80px;overflow:visible;white-space:nowrap;margin:0', 'a very long unbroken sentence that spills out of its box');
  add('p', 'width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0', 'a very long sentence that is cut with an ellipsis');
  add('p', 'width:120px;height:10px;overflow:hidden;margin:0', 'several words that wrap onto more lines than the box is tall');
  add('button', 'width:20px;height:20px;padding:0', 'x');
  add('p', 'color:#777;background:#888;margin:0', 'grey on grey');
  add('p', 'margin:0', 'btn.close app.tab_log');
  add('p', 'margin:0', 'Hello {name}');
  add('p', 'margin:0;font-family:"PT Mono",monospace', 'აბგ');
  const f = new FontFace('MxBad', 'url(/assets/fonts/does-not-exist.woff2)'); document.fonts.add(f); f.load().catch(() => {});
  console.error('selftest console error');
  fetch('/does-not-exist');
  fetch('http://example.invalid/x').catch(() => {});
  setTimeout(() => { throw new Error('selftest page error'); }, 0);
}
"""

SETTLE_JS = "async () => { await document.fonts.ready; await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); return 1; }"


def load_cmaps() -> dict[str, list[tuple[list[tuple[int, int]], set[int]]]]:
    """family -> [(unicode-range intervals, codepoints in the file)], or {} when fonttools is not installed."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return {}
    html = (ROOT / "tezmafia" / "webapp" / "static" / "index.html").read_text(encoding="utf-8")
    out: dict[str, list[tuple[list[tuple[int, int]], set[int]]]] = defaultdict(list)
    for m in re.finditer(r"@font-face\{(.*?)\}", html, re.S):
        body = m.group(1)
        fam = re.search(r'font-family:"([^"]+)"', body)
        url = re.search(r"url\(/assets/fonts/([^)]+)\)", body)
        rng = re.search(r"unicode-range:([^;}]+)", body)
        if not (fam and url and rng):
            continue
        spans = []
        for part in rng.group(1).split(","):
            part = part.strip()[2:]
            lo, _, hi = part.partition("-")
            spans.append((int(lo, 16), int(hi or lo, 16)))
        font = TTFont(str(ROOT / "assets" / "fonts" / url.group(1)))
        out[fam.group(1)].append((spans, set(font.getBestCmap())))
    return dict(out)


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF or cp in (0xFE0F, 0x200D, 0x20E3)


def missing_chars(cmaps: dict, families: list[str], text: str) -> list[str]:
    """Characters that none of the custom faces of the family stack can draw (what falls through to a system font)."""
    gone = []
    for ch in dict.fromkeys(text):
        if ch.isspace() or is_emoji(ch):
            continue
        cp = ord(ch)
        ok = any(
            any(lo <= cp <= hi for lo, hi in spans) and cp in cps
            for fam in families for spans, cps in cmaps.get(fam, [])
        )
        if not ok:
            gone.append(ch)
    return gone


def rel_lum(c: tuple[float, float, float]) -> float:
    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def remeasure(page: Any, found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Contrast over gradients/images: hide the text, sample the real pixels under it, recompute the ratio."""
    import io

    from PIL import Image

    keep = []
    for it in found:
        if it["cat"] != "contrast" or "mxc" not in it:
            keep.append(it)
            continue
        sel = f'[data-mxc="{it["mxc"]}"]'
        x, y, w, h = it["rect"]
        page.evaluate("""s => { const e = document.querySelector(s); if (e) { e.style.setProperty('color', 'transparent', 'important');
            e.style.setProperty('-webkit-text-fill-color', 'transparent', 'important'); e.style.setProperty('text-shadow', 'none', 'important'); } }""", sel)
        try:
            png = page.screenshot(clip={"x": x, "y": y, "width": max(w, 2), "height": max(h, 2)}, full_page=True)
        finally:
            page.evaluate("""s => { const e = document.querySelector(s); if (e) { e.style.removeProperty('color');
                e.style.removeProperty('-webkit-text-fill-color'); e.style.removeProperty('text-shadow'); } }""", sel)
        im = Image.open(io.BytesIO(png)).convert("RGB")
        im = im.crop((2, 2, max(3, im.width - 2), max(3, im.height - 2))).resize((1, 1), Image.BOX)
        bg = im.getpixel((0, 0))
        fg = it["fg"]
        hi, lo = sorted((rel_lum(fg), rel_lum(bg)), reverse=True)
        ratio = (hi + 0.05) / (lo + 0.05)
        if ratio < it["need"]:
            it["detail"] = f"{ratio:.2f}:1 < {it['need']}:1 (sampled pixels)"
            it["ratio"] = round(ratio, 2)
            for k in ("fg", "rect", "mxc"):
                it.pop(k, None)
            keep.append(it)
    return keep


def run_theme(args: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    theme, cfg = args
    from playwright.sync_api import sync_playwright

    base, out_dir = cfg["base"], Path(cfg["out"])
    cmaps = load_cmaps()
    issues: list[dict[str, Any]] = []
    states = 0
    texts: dict[str, list[str]] = {}
    sig_count: Counter[str] = Counter()
    shots = out_dir / f"shots-{cfg['tag']}"
    sheet = out_dir / "sheet"
    shots.mkdir(parents=True, exist_ok=True)
    sheet.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:
            browser = pw.chromium.launch()
        for lang in cfg["langs"]:
            for width in cfg["widths"]:
                ctx = browser.new_context(viewport={"width": width, "height": HEIGHT}, device_scale_factor=2, is_mobile=True,
                                          has_touch=True, reduced_motion="reduce", locale="en-US")
                ctx.add_init_script(f"try{{localStorage.setItem('tm_theme','{theme}')}}catch(e){{}}")
                ctx.route("**/telegram.org/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=""))
                page = ctx.new_page()
                cdp = ctx.new_cdp_session(page)
                cdp.send("DOM.enable")
                cdp.send("CSS.enable")
                events: list[dict[str, Any]] = []
                page.on("console", lambda m, ev=events: ev.append({"cat": "console_error", "detail": m.text[:200]}) if m.type == "error" else None)
                page.on("pageerror", lambda e, ev=events: ev.append({"cat": "page_error", "detail": str(e)[:200]}))
                page.on("requestfailed", lambda r, ev=events: ev.append({"cat": "request_failed", "detail": f"{r.url[-80:]} {r.failure}"}))
                page.on("response", lambda r, ev=events: ev.append({"cat": "http_error", "detail": f"{r.status} {r.url[-80:]}"}) if r.status >= 400 else None)
                page.on("request", lambda r, ev=events: ev.append({"cat": "external_request", "detail": r.url[:100]})
                        if not r.url.startswith((base, "data:", "blob:")) and "telegram.org" not in r.url else None)

                def record(state: str, found: list[dict[str, Any]], count: bool = True, _l: str = lang, _w: int = width) -> None:
                    nonlocal states
                    states += count
                    stamp = f"{theme}-{_l}-{_w}-{state}"
                    for it in found:
                        it.update(theme=theme, lang=_l, width=_w, state=state)
                        issues.append(it)
                    keys = {f"{it['cat']}|{it.get('sel', it['detail'][:40])}" for it in found
                            if it["cat"] not in ("tap_target", "text_truncated")}
                    fresh = [k for k in keys if sig_count[k] < SHOT_CAP]
                    for k in keys:
                        sig_count[k] += 1
                    if fresh:
                        page.screenshot(path=str(shots / f"{stamp}.png"), full_page=True)

                page.goto(f"{base}/?lang={lang}&theme={theme}", wait_until="load")
                page.wait_for_selector("nav.tabs button", timeout=15000)
                page.wait_for_function(f"document.documentElement.getAttribute('data-theme')==='{theme}'")
                page.evaluate(SETTLE_JS)
                page.wait_for_timeout(250)
                startup = [dict(e) for e in events]
                events.clear()
                if startup:
                    record("load", startup, count=False)
                if cfg.get("inject"):
                    page.evaluate(cfg["inject"])
                    page.wait_for_timeout(400)
                    page.evaluate(SETTLE_JS)

                def analyse(state: str, root: str = "body", exclude: str = "") -> None:
                    res = page.evaluate(PAGE_JS, {"root": root, "exclude": exclude})
                    found = remeasure(page, list(res["issues"]))
                    for face in res["bad_faces"]:
                        found.append({"cat": "font_load_error", "sel": "@font-face", "detail": face})
                    if res["fonts"]:
                        doc = cdp.send("DOM.getDocument", {"depth": 0})
                        nodes = cdp.send("DOM.querySelectorAll", {"nodeId": doc["root"]["nodeId"], "selector": "[data-mx]"})["nodeIds"]
                        for f, nid in zip(res["fonts"], nodes, strict=False):
                            try:
                                plat = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": nid})["fonts"]
                            except Exception:
                                continue
                            fb = [x for x in plat if not x["isCustomFont"] and x["glyphCount"] > 0]
                            if not fb:
                                continue
                            fams = [s.strip().strip("\"'") for s in f["family"].split(",")]
                            gone = missing_chars(cmaps, fams, f["shown"]) if cmaps else None
                            if gone == []:
                                continue  # emoji / symbol fonts only
                            found.append({"cat": "glyph_fallback", "sel": f["sel"], "text": f["shown"][:50],
                                          "detail": f"system font {fb[0]['familyName']!r}" + (f", missing {''.join(gone)}" if gone else ""),
                                          "missing": "".join(gone) if gone else ""})
                    found.extend(events)
                    events.clear()
                    tab_texts = texts.setdefault(f"{lang}|{width}|{state}", [])
                    tab_texts.extend(res["texts"])
                    record(state, found)

                for tab in cfg["tabs"]:
                    page.evaluate("t => document.querySelector(`nav.tabs button[data-id=${t}]`).click()", tab)
                    page.evaluate(SETTLE_JS)
                    page.wait_for_timeout(80)
                    analyse(tab, exclude="#customize" if tab == "dossier" else "")
                    if width == 390 and theme in cfg["themes"] and lang in SHEET_LANGS:
                        page.screenshot(path=str(sheet / f"{theme}-{lang}-{tab}.png"))
                # Customize block (lives in the dossier tab).
                page.evaluate("document.querySelector('nav.tabs button[data-id=dossier]').click()")
                page.evaluate("document.getElementById('customize').scrollIntoView()")
                page.evaluate(SETTLE_JS)
                analyse("customize", root="#customize")
                # Language sheet.
                page.evaluate("window.scrollTo(0,0)")
                page.evaluate("document.getElementById('langbtn').click()")
                page.evaluate(SETTLE_JS)
                page.wait_for_timeout(80)
                analyse("langsheet", root="#langwrap")
                if width == 390 and lang in SHEET_LANGS:
                    page.screenshot(path=str(sheet / f"{theme}-{lang}-langsheet.png"))
                page.keyboard.press("Escape")
                ctx.close()
    return {"theme": theme, "issues": issues, "states": states, "texts": texts, "seconds": round(time.time() - t0)}


def summarise(report: dict[str, Any], same_en: dict[str, list[str]]) -> str:
    issues = report["issues"]
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in issues:
        by_cat[it["cat"]].append(it)
    lines = [f"# Mini App matrix ({report['tag']})", "",
             f"States checked: **{report['states']}** (themes {len(report['themes'])} x langs {len(report['langs'])} x widths {len(report['widths'])}"
             f" x [5 tabs + customize + language sheet]); elapsed {report['seconds']}s.", "",
             "| category | issues | distinct | states hit |", "|---|---:|---:|---:|"]
    for cat in sorted(by_cat):
        items = by_cat[cat]
        sigs = {(i.get("sel"), i["detail"] if cat != "tap_target" else "") for i in items}
        hit = {(i["theme"], i["lang"], i["width"], i["state"]) for i in items}
        lines.append(f"| {cat} | {len(items)} | {len(sigs)} | {len(hit)} |")
    lines.append(f"| untranslated (info) | {sum(len(v) for v in same_en.values())} | - | - |")
    lines.append("")
    for cat in sorted(by_cat):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for it in by_cat[cat]:
            groups[f"{it.get('sel', '')} :: {it['detail'] if cat != 'tap_target' else ''}"].append(it)
        lines += [f"## {cat}", ""]
        for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]:
            ex = items[0]
            combos = sorted({f"{i['theme']}/{i['lang']}/{i['width']}/{i['state']}" for i in items})
            extra = ""
            if cat == "tap_target":
                extra = f" smallest {min(i['w'] for i in items)}x{min(i['h'] for i in items)}"
            elif cat == "glyph_fallback":
                extra = f" missing `{''.join(sorted({c for i in items for c in i.get('missing', '')}))}`"
            lines.append(f"- {len(items)}x `{key.strip(' :')[:110]}` e.g. {ex['detail'][:90]}{extra}  -> {', '.join(combos[:3])}")
        lines.append("")
    lines += ["## Strings identical to English (info, not counted as issues)", ""]
    for lang, strs in sorted(same_en.items()):
        lines.append(f"- {lang}: {len(strs)} " + (" | ".join(s[:30] for s in strs[:8]) if strs else ""))
    return "\n".join(lines) + "\n"


def contact_sheets(out_dir: Path) -> list[str]:
    try:
        from PIL import Image
    except ImportError:
        return []
    made = []
    for theme in THEMES:
        cells = [[out_dir / "sheet" / f"{theme}-{lang}-{tab}.png" for tab in [*TABS, "langsheet"]] for lang in SHEET_LANGS]
        if not all(p.exists() for row in cells for p in row):
            continue
        ims = [[Image.open(p) for p in row] for row in cells]
        w, h = ims[0][0].size
        sheet = Image.new("RGB", (w * len(ims[0]), h * len(ims)), "white")
        for r, row in enumerate(ims):
            for c, im in enumerate(row):
                sheet.paste(im, (c * w, r * h))
        sheet = sheet.resize((sheet.width // 2, sheet.height // 2))
        dest = out_dir / f"contact-{theme}-390.png"
        sheet.save(dest)
        made.append(dest.name)
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8797")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--themes", default=",".join(THEMES))
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--widths", default=",".join(map(str, WIDTHS)))
    ap.add_argument("--tabs", default=",".join(TABS))
    ap.add_argument("--selftest", action="store_true", help="inject one defect per check and require every check to fire")
    a = ap.parse_args()
    if a.selftest:
        a.themes, a.langs, a.widths, a.tabs, a.tag = "dossier", "en", "360", "dossier", "selftest"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in (out / f"shots-{a.tag}").glob("*.png") if (out / f"shots-{a.tag}").exists() else []:
        old.unlink()
    themes = a.themes.split(",")
    cfg = {"tag": a.tag, "base": a.base, "out": str(out), "langs": a.langs.split(","), "widths": [int(x) for x in a.widths.split(",")],
           "tabs": a.tabs.split(","), "themes": themes, "inject": SELFTEST_JS if a.selftest else ""}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=min(a.workers, len(themes))) as pool:
        results = list(pool.map(run_theme, [(t, cfg) for t in themes]))
    issues = [i for r in results for i in r["issues"]]
    # Untranslated: dossier theme leaf strings (theme-independent text) that equal the English ones, per language.
    texts = {k: v for r in results if r["theme"] == themes[0] for k, v in r["texts"].items()}
    same_en: dict[str, list[str]] = {}
    for lang in cfg["langs"]:
        if lang == "en":
            continue
        mine, eng = set(), set()
        for k, v in texts.items():
            lg, w, _ = k.split("|")
            if w != "390":
                continue
            if lg == lang:
                mine.update(v)
            elif lg == "en":
                eng.update(v)
        same_en[lang] = sorted(s for s in mine & eng if not SAME_OK.match(s) and len(re.findall(r"[^\W\d_]", s)) >= 3)
    report = {"tag": a.tag, "states": sum(r["states"] for r in results), "themes": themes, "langs": cfg["langs"],
              "widths": cfg["widths"], "seconds": round(time.time() - t0), "issues": issues, "untranslated_same_as_en": same_en}
    (out / f"report-{a.tag}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / f"summary-{a.tag}.md").write_text(summarise(report, same_en), encoding="utf-8")
    sheets = contact_sheets(out)
    print(f"{report['states']} states, {len(issues)} issues, {len(sheets)} contact sheets, {report['seconds']}s -> {out}")
    if a.selftest:
        want = {"overflow_doc", "overflow_el", "text_overflow", "text_truncated", "text_clipped", "tap_target", "contrast", "raw_key",
                "placeholder", "glyph_fallback", "font_load_error", "console_error", "page_error", "http_error", "request_failed",
                "external_request"}
        got = {i["cat"] for i in issues}
        print("selftest:", "OK, every check fired" if want <= got else f"MISSED {sorted(want - got)}")
        return 0 if want <= got else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
