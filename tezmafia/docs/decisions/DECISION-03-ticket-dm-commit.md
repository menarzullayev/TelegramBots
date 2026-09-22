# DECISION-03 — next_role consume vs DM-fail

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `ticket-dm-fail`)  
**Depends on:** DECISION-01, DECISION-02

## Qaror

Variant **D — Consume-after-DM.**

`apply_role_tickets` faqat peek + xotirada swap (DECISION-02 first-wins).  
`take_next_role` va refund **faqat** barcha role DM muvaffaqiyatli bo‘lgach (`commit_role_tickets`).  
Birorta DM fail → `cancel`; ticket queue va pul o‘zgarmaydi. Loadout bilan bir xil: iqtisod faqat o‘yin haqiqatan boshlangach.

## Sabab

`start()` dan keyin kimdir botga `/start` bermagan bo‘lsa o‘yin bekor. Ticketni oldin yo‘qotish $35 ni inventardan farq qilardi. Live next_role E2E shu cancel yo‘lida yiqilardi.

## Trade-off

Peek → DM → commit orasida `next_role` o‘zgarsa (boshqa o‘yin `take`), commit bo‘sh olinishi mumkin. Single-node + `App.lock` da bu yo‘l yopiq. Refund faqat `take` muvaffaqiyatli bo‘lsa.

## Ta’sir

- `tezmafia/bot.py` — `apply_role_tickets` peek; `commit_role_tickets`; `start_game` tartibi
- `docs/decisions/DECISION-02-next-role-assign.md` — consume vaqti shu qarorga o‘tdi
- test: `tests/test_bot_e2e.py`
