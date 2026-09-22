# DECISION-12 — Bot profil matnlari uz

**Status:** accepted  
**Date:** 2026-09-22  
**Decider:** user (AskUserQuestion `profile-i18n`)  
**Depends on:** DECISION-09

## Qaror

Variant **A — Short description va description uz qoladi** (`data/.profile_ok` marker bilan bir martalik set).

`setMyCommands` 11 til (DECISION-09) alohida; profil “about” bloklari global uz.

## Sabab

SetMyName flood (2026-09-21) va ko‘p tilli profil API xarajati hozir prioritet emas. Gameplay + command menu i18n yetarli.

## Trade-off

Telegram app tili ≠ uz bo‘lsa, bot kartochkasi uz; `/settings` va menyu tilga mos.

## Ta’sir

- `tezmafia/bot.py` — `setup_bot_profile` o‘zgarishsiz
- Kod o‘zgarishi yo‘q

## Validation (2026-09-22)

| Tekshiruv | Natija                                       |
| --------- | -------------------------------------------- |
| Qaror     | kod diff yo‘q                                |
| pytest    | **163/163** (DECISION-11 bilan bir xil tree) |
| qa_gate   | **100/100**                                  |

**Baseline → after:** profil uz (o‘zgarish yo‘q).

**Qolgan risk:** EN foydalanuvchi bot kartochkasida uz ko‘radi.
