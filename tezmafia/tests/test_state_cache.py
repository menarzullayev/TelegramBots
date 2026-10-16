"""Stale-while-revalidate ranking cache and the Mini App warm-up: no request waits on a slow query twice."""

from __future__ import annotations

import asyncio
import time

import pytest

from tezmafia.db import Store


@pytest.fixture
async def store(tmp_path):
    s = Store(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    await s.init()
    s.cache_ttl = 60.0
    yield s
    await s.engine.dispose()


def _age(store: Store, key: object, seconds: float) -> None:
    at, value = store._cache[key]
    store._cache[key] = (at - seconds, value)


@pytest.mark.asyncio
async def test_stale_value_is_served_at_once_and_refreshed_in_background(store: Store) -> None:
    calls = 0
    gate = asyncio.Event()

    async def slow() -> int:
        nonlocal calls
        calls += 1
        if calls > 1:
            await gate.wait()  # the refresh is slow; the caller must not wait for it
        return calls

    assert await store.cached("k", slow) == 1  # a cold cache computes once
    _age(store, "k", 61)
    started = time.monotonic()
    assert await asyncio.wait_for(store.cached("k", slow), 1) == 1  # stale: old value, no waiting
    assert await asyncio.wait_for(store.cached("k", slow), 1) == 1  # one refresh in flight, not two
    await asyncio.sleep(0)  # let the refresh task start
    assert time.monotonic() - started < 0.5 and calls == 2
    gate.set()
    await asyncio.sleep(0.05)
    assert await store.cached("k", slow) == 2  # the background refresh landed


@pytest.mark.asyncio
async def test_failed_refresh_keeps_the_stale_value(store: Store) -> None:
    async def ok() -> str:
        return "old"

    async def broken() -> str:
        raise RuntimeError("db hiccup")

    await store.cached("k", ok)
    _age(store, "k", 61)
    assert await store.cached("k", broken) == "old"
    await asyncio.sleep(0.05)
    assert not store._refreshing  # a failed refresh clears its in-flight mark, so a later call retries
    assert await store.cached("k", broken) == "old"


@pytest.mark.asyncio
async def test_funnel_counts_in_one_pass(store: Store) -> None:
    from tezmafia.db import GameRow

    now = time.time()
    rows = [  # (chat, night_no, winner): lobby only, started, finished x2 in chat 1, finished once in chat 2
        (1, 0, None), (1, 1, None), (1, 2, "town"), (1, 3, "mafia"), (2, 1, "town"),
    ]
    async with store.session() as s:
        for i, (chat, night, winner) in enumerate(rows):
            payload = {"night_no": night} | ({"winner": winner} if winner else {})
            import json

            s.add(GameRow(id=f"g{i}", chat_id=chat, status="x", payload=json.dumps(payload), version=1,
                          created_at=now - 10, updated_at=now))
        await s.commit()
    f = await store.funnel(now - 3600)
    assert (f["lobbies"], f["started"], f["finished"], f["repeat"]) == (5, 4, 3, 1)
