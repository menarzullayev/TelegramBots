# DECISION-05 — Host-menu: 11 til + Enter-chat

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `e2e-goal-close`)  
**Depends on:** DECISION-04

## Qaror

Variant **C — TrueMafia/MafiaAz host UX ni TezMafia ga ko‘chirish.**

1. Til tanlash: MafiaAz dagi **11 kod** (`az tr en ru ua kz uz kg tj id br`).
2. DM `/start` (payload yo‘q): TrueMafia host menyu — guruhga qo‘sh, **Stolga kirish**, til, profil, rollar.
3. Enter-chat: foydalanuvchining ochiq stollari + `startgroup` havola.

Gameplay matnlari hozircha o‘zbekcha qoladi (to‘liq 11×21 tarjima — alohida qaror). Til kodi `prefs` da saqlanadi.

## Sabab

DECISION-04 katalogi inline callback TimeoutError ni o‘lchadi; yetishmayotgan UX — 3 til vs 11 va «Enter the chat». Goal ochiq, lekin UX shu qarorda yopiladi.

## Trade-off

11 til picker ≠ 11 til gameplay. Donate/IAP yo‘q. Enter-chat faqat sqlite `unfinished` o‘yinlar + add-URL (TrueMafia global chat-list emas).

## Ta’sir

- `tezmafia/i18n.py` — LANGS
- `tezmafia/db.py` — `set_lang` 11 kod
- `tezmafia/keyboards.py` — `lang_kb`, `host_kb`, `chats_kb`
- `tezmafia/bot.py` — `/start` host menyu, `m:chats`, `/chats` `/enter`
- `tezmafia/texts.py` — host/chats
- `tests/test_handlers_remaining.py` — `cmd_chats` + `m:chats`
- `tezmafia.service` PID **1712228** → **1718842** (`/chats` live)

## Validation (2026-09-21)

| Tekshiruv                | Natija                                                                                 |
| ------------------------ | -------------------------------------------------------------------------------------- |
| pytest                   | **156/156**                                                                            |
| qa_gate                  | **100/100**                                                                            |
| `/start` (1777924)       | host menyu: guruhga qo‘sh, Stolga kirish `m:chats`, Til, Profil/Rollar                 |
| `/settings` (1777926)    | 11 til, uz primary                                                                     |
| `/chats` empty (1777928) | «Ochiq stol yo‘q» + `startgroup` (sqlite unfinished=0; `g_sODQ5fp3j-U` finished 23:22) |
| Lab `/mafia` (163)       | lobby `g_0ZxOw6urRb4` 1/16                                                             |
| `/chats` live (1777930)  | «ochiq stollaringiz: 1» + `Stol lobby · 1p` → `?start=g_0ZxOw6urRb4`                   |
| `/enter` (1777932)       | `/chats` bilan bir xil                                                                 |
| Donate                   | klon qilinmadi                                                                         |

**Baseline → after:** til 3 kod (`uz/ru/en`) → 11 kod picker; Enter-chat yo‘q → `/chats`/`/enter` + `m:chats` (callback MCP TimeoutError; matn yo‘li o‘lchangan).

**Qolgan risk:** `m:chats` Kurigram `request_callback_answer` timeout (tool, bot emas). TrueMafia global chat-list yo‘q. Gameplay 11×21 tarjima — keyingi qaror.
