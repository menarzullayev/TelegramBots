# DECISION-09 — setMyCommands 11 til

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `bot-commands-i18n`)  
**Depends on:** DECISION-06

## Qaror

Variant **B — 11 til uchun `setMyCommands(language_code=…)`.**

Default (til yo‘q) = uz. MafiaAz kodi → Telegram ISO: `ua→uk`, `kz→kk`, `kg→ky`, `tj→tg`, `br→pt`.

## Sabab

Gameplay 11 til (DECISION-06), lekin / menyu global uz edi. `language_code` shu teshikni yopadi.

## Trade-off

Har til × 3 scope = ko‘p API chaqiriq; hash-marker bilan qayta restart flood qilmaydi. `pt` barcha portugal klientlariga ketadi (faqat BR emas).

## Ta’sir

- `tezmafia/i18n.py` — `TG_LANG`, `cmd()`
- `tezmafia/bot.py` — `_sync_bot_commands`
- `tezmafia.service` PID **1828079** → **1840047**

## Validation (2026-09-21)

| Tekshiruv                    | Natija                        |
| ---------------------------- | ----------------------------- |
| pytest                       | **161 → 162**                 |
| qa_gate                      | **100/100**                   |
| `getMyCommands` default/`uz` | «Yangi o‘yin ochish»          |
| `getMyCommands` `en`         | «Open a new game»             |
| `getMyCommands` `uk` (ua)    | «Нова гра»                    |
| `getMyCommands` `pt` (br)    | «Abrir novo jogo»             |
| marker                       | `data/.commands_2cdd0aa337bb` |
| Flood                        | yangi restartda yo‘q          |

**Baseline → after:** 3 scope × 1 til (uz) → 3 scope × (default uz + 11 `language_code`).

**Qolgan risk:** klient `language_code` Telegram app tiliga bog‘liq, bot `/settings` tiliga emas. `setMyName` 24s flood (20:12) — about matnlar hali uz.
