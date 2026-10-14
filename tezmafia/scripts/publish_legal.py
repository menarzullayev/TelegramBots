"""Publish docs/legal/*.md to telegra.ph and record the page URLs for the bot.

First run creates a Telegraph account (token kept in data/.telegraph.json, never committed) and
one page per document; later runs edit the same pages. URLs go to tezmafia/legal_urls.json.

Usage (from the tezmafia directory):  python -m scripts.publish_legal
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "legal"
URLS = ROOT / "tezmafia" / "legal_urls.json"
STATE = ROOT / "data" / ".telegraph.json"
API = "https://api.telegra.ph"


def _call(method: str, **params: object) -> dict:
    data = urllib.parse.urlencode(
        {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in params.items()}
    ).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=30) as resp:
        body = json.loads(resp.read())
    if not body.get("ok"):
        raise RuntimeError(f"telegraph {method}: {body.get('error')}")
    return body["result"]


def _inline(text: str) -> list:
    """Plain text with bare URLs turned into links (commands like /privacy stay text)."""
    nodes: list = []
    for part in re.split(r"(https?://\S+)", text):
        if not part:
            continue
        nodes.append({"tag": "a", "attrs": {"href": part}, "children": [part]} if part.startswith("http") else part)
    return nodes


def to_nodes(markdown: str) -> tuple[str, list]:
    """Tiny Markdown subset → Telegraph nodes: '# title', '## h', '- item', paragraphs."""
    title, nodes, items = "", [], []

    def flush() -> None:
        if items:
            nodes.append({"tag": "ul", "children": [{"tag": "li", "children": _inline(i)} for i in items]})
            items.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            nodes.append({"tag": "h3", "children": [line[3:].strip()]})
        elif line.startswith("- "):
            items.append(line[2:].strip())
        elif line:
            flush()
            nodes.append({"tag": "p", "children": _inline(line)})
        else:
            flush()
    flush()
    return title, nodes


def main() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if "token" not in state:
        acc = _call("createAccount", short_name="TezMafia", author_name="TezMafia", author_url="https://t.me/qorashahar_mafia_bot")
        state = {"token": acc["access_token"], "pages": {}}
    urls: dict[str, dict[str, str]] = json.loads(URLS.read_text(encoding="utf-8")) if URLS.exists() else {}
    for doc in sorted(DOCS.glob("*.md")):
        kind, lang = doc.stem.split(".")
        title, content = to_nodes(doc.read_text(encoding="utf-8"))
        common = {"access_token": state["token"], "title": title, "content": content, "author_name": "TezMafia",
                  "author_url": "https://t.me/qorashahar_mafia_bot"}
        path = state["pages"].get(doc.stem)
        page = _call(f"editPage/{path}", **common) if path else _call("createPage", **common)
        state["pages"][doc.stem] = page["path"]
        urls.setdefault(kind, {})[lang] = page["url"]
        print(f"{doc.stem}: {page['url']}")
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    URLS.write_text(json.dumps(urls, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
