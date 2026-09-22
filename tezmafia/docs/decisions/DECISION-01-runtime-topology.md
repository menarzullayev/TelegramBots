# DECISION-01 — Runtime va persistens

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `runtime-topology`)

## Qaror

Variant **A — Single-node muzlatish.**

TezMafia production shartnomasi:

- bitta systemd process (`tezmafia.service`)
- `asyncio.Lock` (`App.lock`) — o‘yin mutatsiyasi
- in-memory `Game` + sqlite snapshot (`Store` / `games.payload`)
- long polling (`dp.start_polling`)
- Redis yo‘q, webhook yo‘q, Postgres yo‘q

## Sabab

O‘lchangan bottleneck yo‘q (lab 5–12 o‘yinchi). B/C Store, `recover`, timer va QA-16..20 ni spekulativ rewrite qilardi.

## Trade-off

Horizontal scale va multi-worker yo‘q. Soak/volume/1M row shu kontrakt ichida lokal qoladi.

## Ta’sir

- `tezmafia/config.py` — `database_url` faqat `sqlite*`
- `tezmafia/bot.py` — polling; `set_webhook` qo‘shilmasin
- `tezmafia/db.py` — aiosqlite
- QA-21, QA-22, QA-37 shu shartnomani ushlab turadi

## Keyingi o‘zgarish

Multi-instance yoki o‘lchangan sqlite/polling limit bo‘lsa — yangi DECISION. Shu faylni o‘zgartirmasdan Postgres/Redis/webhook kiritilmasin.

**DECISION-10 (2026-09-22):** Telegram Serverless JS rewrite rad etildi. Production Python + polling qoladi.
