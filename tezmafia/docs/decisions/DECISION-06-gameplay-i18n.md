# DECISION-06 — Competitor E2E: to‘liq 11×21 gameplay i18n

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `e2e-goal-close`)  
**Depends on:** DECISION-05

## Qaror

Variant **C — Maqsad ochiq. To‘liq 11×21 gameplay + faza matnlarini tarjima qil.**

1. 21 rol: nom + katalog kartasi + rol DM.
2. Fazalar: lobby, tun, kun, sud, lynch, game-over, last-words.
3. Yon matnlar: shop item, profile, help, host/menu tugmalari, action/start sabablari.
4. Til manbasi: guruh xabari → `get_lang(chat_id)`; DM → `get_lang(user_id)`.
5. Noma’lum kalit → `uz` fallback. `ROLE_UZ` / `ROLE_CARDS` uz manba sifatida qoladi (QA-67).

## Sabab

DECISION-05 C host picker ni yopdi, lekin foydalanuvchi E2E maqsadini 11 til gameplay siz yopishni rad etdi. Noto‘g‘ri qisman tarjima (faqat host) keyin ikki qatlamli copy yaratadi.

## Trade-off

Katta content yuzasi; tarjima sifati machine+review. Donate/IAP yo‘q. Guruh matni bitta chat tilida — stol aralash tilli bo‘lishi mumkin.

## Ta’sir

- `tezmafia/i18n.py` — `t()` / `role_title`
- `tezmafia/locales/*.json` — 11 katalog
- `tezmafia/texts.py` — `lang=` (default `uz`)
- `tezmafia/roles.py` — `public_counts(lang)`
- `tezmafia/shop.py` — `resolve_role` barcha til nomlari
- `tezmafia/keyboards.py` — tilga bog‘liq tugmalar
- `tezmafia/bot.py` — `lang` ulash
- `tests/test_i18n_catalog.py`
- `tezmafia.service` PID **1718842** → **1803316**

## Validation (2026-09-21)

| Tekshiruv                | Natija                                                                 |
| ------------------------ | ---------------------------------------------------------------------- |
| Katalog                  | 11 til × **223** kalit, `missing_keys=[]`                              |
| pytest                   | **156 → 160**                                                          |
| qa_gate                  | **100/100**                                                            |
| `/roles` EN (1777935)    | «Qorashahar — roles» + 21 tugma (`Detective`, `Citizen`, `Black Hand`) |
| `/settings` EN (1777938) | «Game text in this language.»                                          |
| `/start` EN (1777939)    | «referee bot for groups» + Join table / Profile / Roles                |
| Donate                   | klon qilinmadi                                                         |

**Baseline → after:** gameplay faqat uz → `t(lang)` + 11 JSON; live DM `en` `/roles` Komissar o‘rniga Detective.

**Qolgan risk:** kz/kg/tj tarjima review yo‘q. Live 5p rol DM hali faqat uz (DECISION-04). Guruh vs user til ajratilgan. ~~`lang_kb` primary doim `uz`~~ → **DECISION-11:** joriy til PRIMARY.
