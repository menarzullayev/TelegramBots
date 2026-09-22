# DECISION-11 — lang_kb: joriy til PRIMARY

**Status:** accepted  
**Date:** 2026-09-22  
**Decider:** user (AskUserQuestion `lang-kb-primary`)  
**Depends on:** DECISION-06

## Qaror

Variant **A — `lang_kb(current)` joriy `/settings` tilini PRIMARY qiladi.**

## Sabab

DECISION-06 gameplay `get_lang(user_id)` / guruh tiliga bog‘liq. Doim `uz` yorqin bo‘lishi EN (va boshqalar) tanlanganda noto‘g‘ri UX.

## Trade-off

Guruh tili ≠ foydalanuvchi tili bo‘lsa, DM `/settings` o‘z tilini ko‘rsatadi (to‘g‘ri kontrakt).

## Ta’sir

- `tezmafia/keyboards.py` — `lang_kb(lang="uz")`
- `tezmafia/bot.py` — `cmd_settings`, `cb_lang` → `lang_kb(lang)`
- `tests/test_city_roles.py` — en primary assert

## Validation (2026-09-22)

| Tekshiruv       | Natija                         |
| --------------- | ------------------------------ |
| pytest          | **163/163**                    |
| qa_gate         | **100/100**                    |
| `lang_kb("en")` | faqat EN tugma `style=primary` |

**Baseline → after:** PRIMARY doim `uz` → joriy `lang`.

**Qolgan risk:** noma’lum `lang` → fallback `uz` PRIMARY.

**Live:** `tezmafia.service` restart → PID **1840047** → **90721** (2026-09-22).
