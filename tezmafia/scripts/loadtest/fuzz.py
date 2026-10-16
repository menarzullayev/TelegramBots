"""Play N random games on all cores and summarise rule violations and games that never end.

    python -m scripts.loadtest.fuzz [--games 1000000] [--workers 22] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from multiprocessing import Pool


def _batch(job: tuple[range, bool]) -> tuple[int, int, Counter, Counter, dict, Counter, Counter, Counter, Counter]:
    from scripts.loadtest.sim import play

    seeds, extras = job
    notes: Counter = Counter()
    shape: Counter = Counter()

    nights = 0
    stalled = 0
    viol: Counter = Counter()
    stall_kind: Counter = Counter()
    examples: dict = {}
    winners: Counter = Counter()
    sizes: Counter = Counter()
    for s in seeds:
        r = play(s, extras=extras)
        notes.update(r.notes)
        shape["with_bots"] += r.bots > 0
        shape["bots_total"] += r.bots
        shape["games_with_kicks"] += r.kicks > 0
        shape["kicks_total"] += r.kicks
        nights += r.nights
        sizes[len(r.game.players)] += 1
        winners[r.game.winner or "-"] += 1
        for v in r.violations:
            key = v.split(": ", 1)[1][:70]
            viol[key] += 1
            examples.setdefault(key, s)
        if r.stalled:
            stalled += 1
            kind = "everyone dead" if not r.game.alive_players() else "alive: " + ",".join(
                sorted(p.role for p in r.game.alive_players()))
            stall_kind[kind] += 1
            examples.setdefault(kind, s)
    return nights, stalled, viol, stall_kind, examples, winners, sizes, notes, shape


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1_000_000)
    ap.add_argument("--workers", type=int, default=22)
    ap.add_argument("--json")
    ap.add_argument("--classic", action="store_true", help="only the original simulator (no bots/kicks/tickets/...)")
    args = ap.parse_args()
    step = 2000
    t0 = time.perf_counter()
    nights = stalled = 0
    viol: Counter = Counter()
    stall_kind: Counter = Counter()
    winners: Counter = Counter()
    sizes: Counter = Counter()
    notes: Counter = Counter()
    shape: Counter = Counter()
    examples: dict = {}
    with Pool(args.workers) as pool:
        jobs = [(range(a, min(args.games, a + step)), not args.classic) for a in range(0, args.games, step)]
        for i, (n, st, v, sk, ex, w, sz, nt, sh) in enumerate(pool.imap_unordered(_batch, jobs)):
            notes.update(nt)
            shape.update(sh)
            nights += n
            stalled += st
            viol.update(v)
            stall_kind.update(sk)
            winners.update(w)
            sizes.update(sz)
            for k, s in ex.items():
                examples.setdefault(k, s)
            if i % 50 == 0:
                done = min(args.games, (i + 1) * step)
                print(f"  ~{done:,} games, {done / (time.perf_counter() - t0):,.0f}/s", flush=True)
    wall = time.perf_counter() - t0
    out = {
        "games": args.games, "wall_s": round(wall, 1), "games_per_s": round(args.games / wall),
        "avg_nights": round(nights / args.games, 2), "stalled": stalled,
        "violations": dict(viol.most_common()), "stalled_kinds": dict(stall_kind.most_common(15)),
        "winners": dict(winners.most_common()), "examples(seed)": examples,
        "extras": not args.classic, "notes": dict(notes.most_common()), "shape": dict(shape),
    }
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
