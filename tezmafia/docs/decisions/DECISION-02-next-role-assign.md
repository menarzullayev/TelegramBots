# DECISION-02 — next_role assignment

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `next-role-assign`)  
**Depends on:** DECISION-01

## Qaror

Variant **B — First-wins + refund.**

`apply_role_tickets` o‘rindiq tartibida (`game.players`):

1. Ticket peek qilinadi (consume vaqti — DECISION-03).
2. O‘yinchida allaqachon shu rol bo‘lsa — muvaffaqiyat; rol **claimed**.
3. Rol bu o‘yinda allaqachon claimed bo‘lsa — **$35 refund**, swap yo‘q.
4. Sumkada/rol yo‘q (hech kimda yo‘q) — **$35 refund**.
5. Boshqa o‘yinchida bor — **swap** + claimed.

## Sabab

Bag va faction soni saqlanadi. Ikkinchi «komissar» ticket birinchini o‘g‘irlamaydi; iqtisod oldindan aytiladi.

## Trade-off

Xaridor o‘rindiq 2+ da bo‘lsa, o‘rindiq 1 ticketidan yutqazadi (seat order = first). Rolni bag‘ga majburan qo‘yish yo‘q.

## Ta’sir

- `tezmafia/bot.py` — `App.apply_role_tickets`
- test: `tests/test_bot_e2e.py`
