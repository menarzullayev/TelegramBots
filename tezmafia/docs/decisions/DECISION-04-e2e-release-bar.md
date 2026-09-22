# DECISION-04 — Competitor E2E release bar

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `e2e-release-bar`)  
**Depends on:** DECISION-01, DECISION-02, DECISION-03

## Qaror

Variant **D — Live 5p VA to‘liq competitor katalog** (shu sessiyada, bitta release bar).

Maqsad yopilishi uchun ikkala dalil ham kerak:

1. Lab live 5p: `tezmafia.service` yangi kodda; `next_role` apply; loadout; N1 komissar otish yo‘q.
2. `@TrueMafiaBot` va `@MafiaAzBot` host-menu / yetiladigan buyruqlar katalogi bosib chiqiladi (donate/IAP klon qilinmaydi).

`qa_gate` 100/100 yetarli emas.

## Sabab

Data/State qotdi; live Telegram xatti-harakati va raqib UX hali o‘lchanmagan. D ikkala bo‘shliqni bir bar qiladi — parallel mustaqil decision emas, bitta acceptance scope.

## Trade-off

Keng scope: servis restart + 5 akkaunt + raqib menyu. Host-menu TimeoutError (Kurigram callback) bo‘lsa buyruq/deep-link bilan yopiladi. Donate klon yo‘q.

## Ta’sir

- `tezmafia.service` restart (PID 1553220 → **1672943**, 23:13:41 +05)
- live Lab `-1004307184963` o‘yin `g_sODQ5fp3j-U`
- `docs/competitor-matrix.md`

## Validation (2026-09-21)

| Tekshiruv                   | Natija                                       |
| --------------------------- | -------------------------------------------- |
| Service DECISION-01 log     | polling + sqlite                             |
| Host ticket                 | Komissar DM + N1 `nd:` only                  |
| Seat-2 ticket               | citizen + $35 refund (`/profile`)            |
| Loadout mask                | inventar `{}`, `shop_mask=True`              |
| Tun-1                       | miss → Kun 1                                 |
| TrueMafia/MafiaAz buyruqlar | `/help` `/profile` `/shop` `/roles` `/start` |
| Inline callback             | TimeoutError — buyruq fallback               |
| Donate                      | klon qilinmadi                               |
