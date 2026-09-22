# DECISION-08 — Recover: 30s grace

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `restart-recover`)  
**Depends on:** DECISION-01, DECISION-07

## Qaror

Variant **B — Recover: muddati o‘tgan bo‘lsa kamida 30s grace, keyin resolve.**

`recover()` endi NIGHT/DAY/VOTING/LYNCH/LOBBY da `deadline <= now` bo‘lsa darhol `_timed_*` chaqirmaydi. `deadline = now + 30`, persist, `schedule`.

`ROLE_ASSIGNMENT` o‘zgarishsiz: start chala qolgan bo‘lsa `enter_night`.

## Sabab

DECISION-05 restart `g_sODQ5fp3j-U` ni Tun-2 AFK GO qildi. Deploy o‘yinni jim o‘ldirmasligi kerak.

## Trade-off

Faza 30s kechikadi. Host `/next` hali ham skip qiladi. 30s qattiq konstanta (sozlama emas).

## Ta’sir

- `tezmafia/bot.py` — `RECOVER_GRACE`, `recover()`
- recover testlari / QA-40
- `tezmafia.service` PID **1803316** → **1828079**

## Validation (2026-09-21)

| Tekshiruv                         | Natija                                                 |
| --------------------------------- | ------------------------------------------------------ |
| `test_recover_expired_gets_grace` | NIGHT qoladi, `deadline ≈ now+30`, timer bor           |
| QA-40                             | NIGHT + future deadline (oldingi “darhol DAY/GO” yo‘q) |
| pytest                            | **160 → 161**                                          |
| qa_gate                           | **100/100**                                            |

**Baseline → after:** expired recover → darhol `_timed_*`. Endi `+30s` schedule. ROLE_ASSIGNMENT o‘zgarishsiz.

**Qolgan risk:** 30s ichida ikkinchi restart yana grace beradi (o‘yin cho‘zilishi mumkin). `/next` grace ni chetlab o‘tadi.
