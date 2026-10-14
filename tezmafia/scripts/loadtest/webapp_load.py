"""Mini App API under concurrent load: the real aiohttp app on a spare local port, signed initData.

    python -m scripts.loadtest.webapp_load --db PATH [--levels 10,100,500] [--requests 2000]

Measures /api/state latency and throughput per concurrency level, then checks that forged or
missing initData is refused (401) and that a badge-spamming user is cut off (429).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import random
import statistics
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

from scripts.loadtest.generate import FAKE_USER

TOKEN = "1234567:LOADTEST_TOKEN_NOT_REAL"
PORT = 8798


def init_data(user_id: int, token: str = TOKEN, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH" + str(user_id),
        "user": json.dumps({"id": user_id, "first_name": "Load", "language_code": "uz"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--levels", default="10,100,500")
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--json")
    args = ap.parse_args()

    from tezmafia.db import Store
    from tezmafia.webapp.server import build_app

    store = Store(f"sqlite+aiosqlite:///{args.db}")
    store.cache_ttl = 60.0  # as the running bot does
    fake_app = SimpleNamespace(store=store, settings=SimpleNamespace(bot_token=TOKEN))
    runner = web.AppRunner(build_app(fake_app), access_log=None)  # type: ignore[arg-type]
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start()
    base = f"http://127.0.0.1:{PORT}"
    rng = random.Random(3)
    n_users = 1_000_000
    report: dict = {"levels": []}

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as http:
        for level in [int(x) for x in args.levels.split(",")]:
            lat: list[float] = []
            codes: dict[int, int] = {}
            sem = asyncio.Semaphore(level)

            async def one(http=http, sem=sem, lat=lat, codes=codes) -> None:
                uid = FAKE_USER + int(rng.random() ** 2 * (n_users - 10))
                async with sem:
                    t0 = time.perf_counter()
                    async with http.get(f"{base}/api/state", headers={"Authorization": "tma " + init_data(uid)}) as r:
                        await r.read()
                        codes[r.status] = codes.get(r.status, 0) + 1
                    lat.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            await asyncio.gather(*(one() for _ in range(args.requests)))
            wall = time.perf_counter() - t0
            lat.sort()
            row = {"concurrency": level, "requests": args.requests, "rps": round(args.requests / wall, 1),
                   "p50_ms": round(statistics.median(lat), 1), "p95_ms": round(lat[int(len(lat) * 0.95)], 1),
                   "max_ms": round(lat[-1], 1), "status": codes}
            report["levels"].append(row)
            print(json.dumps(row), flush=True)

        # security under load
        async with http.get(f"{base}/api/state", headers={"Authorization": "tma " + init_data(FAKE_USER + 5, "9:WRONG")}) as r:
            forged = r.status
        async with http.get(f"{base}/api/state") as r:
            missing = r.status
        stale_header = "tma " + init_data(FAKE_USER + 5, auth_date=int(time.time()) - 2 * 86400)
        async with http.get(f"{base}/api/state", headers={"Authorization": stale_header}) as r:
            stale = r.status
        spam = []
        for _ in range(15):
            async with http.post(f"{base}/api/badge", json={"key": "off"},
                                 headers={"Authorization": "tma " + init_data(FAKE_USER + 6)}) as r:
                spam.append(r.status)
        report["security"] = {"forged": forged, "missing": missing, "stale_2d": stale, "badge_spam_codes": spam}
        print(json.dumps(report["security"]), flush=True)
    await runner.cleanup()
    await store.engine.dispose()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
