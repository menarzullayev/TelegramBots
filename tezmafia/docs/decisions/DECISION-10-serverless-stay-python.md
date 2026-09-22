# DECISION-10 — Telegram Serverless: Python qoladi

**Status:** accepted  
**Date:** 2026-09-22  
**Decider:** user (AskUserQuestion `js-rewrite-scope`)  
**Depends on:** DECISION-01  
**Research:** [../research-telegram-serverless-2026-09-22.md](../research-telegram-serverless-2026-09-22.md)

## Qaror

Variant **A — Production Python qoladi; JS rewrite yo‘q.**

`@qorashahar_mafia_bot` DECISION-01 kontraktida qoladi: systemd + sqlite + long polling + in-process timer. Telegram Serverless yoqilgan bo‘lsa ham `tgcloud push` / `webhook sync` qilinmaydi.

## Sabab

Serverless V8 isolate ichida TezMafia soati yo‘q:

- `setTimeout` aniqlanmagan
- CPU ~3s da `CPU timer exceeded`
- `Atomics.wait` ~11s da o‘ladi
- `cron` / `schedule` handler turi yo‘q
- Bot API `sendMessage` da `schedule_date` yo‘q

Tashqi tick = yana bir vendor, “xarajat nol” emas. Narx rasmiy docsda yo‘q. Hozirgi host allaqachon $0 incremental.

## Trade-off

VPS/host ijarasi kelajakda ham shu mashinada qoladi. Serverless’dagi JS/sqlite tekin hosting ishlatilmaydi. BotFather’da Serverless flag yoqilgan holda qolishi mumkin — lekin deploy qilinmasa webhook pollingni ololmaydi.

## Ta’sir

- `tezmafia/bot.py` — `assert_polling_contract`: webhook bo‘lsa poll boshlanmaydi (host only, path yozilmaydi)
- `docs/research-telegram-serverless-2026-09-22.md`
- Production PID **1840047** o‘zgarishsiz

## Taqiqlangan

- Production botga `npx tgcloud push` / `webhook sync`
- Shu bot tokeni bilan JS cutover
- `set_webhook` (QA-21)

## Validation (2026-09-22)

| Tekshiruv                              | Natija                        |
| -------------------------------------- | ----------------------------- |
| `getWebhookInfo`                       | url empty, pending 0          |
| `tezmafia.service`                     | active, PID **1840047**       |
| isolate sleep (`tgcloud run`, no push) | 45s/90s imkonsiz              |
| `assert_polling_contract`              | empty url OK; host-only error |

**Baseline → after:** runtime o‘zgarmadi. Startup webhook guard qo‘shildi.

**Qolgan risk:** birov `tgcloud push` qilsa webhook o‘rnatiladi; keyingi restart `RuntimeError` bilan to‘xtaydi (jimong polling yo‘q).
