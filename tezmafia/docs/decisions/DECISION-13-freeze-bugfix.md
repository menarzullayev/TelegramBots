# DECISION-13 — Freeze: faqat bugfix

**Status:** accepted  
**Date:** 2026-09-22  
**Decider:** user (AskUserQuestion `next-sprint`)  
**Depends on:** DECISION-07, DECISION-10

## Qaror

Variant **A — Feature freeze.** Yangi product scope yo‘q; faqat bugfix, regressiya, xavfsizlik, operatsion zarurat.

## Sabab

Competitor E2E bar yopilgan (DECISION-07). Runtime i18n + host UX yetarli. Serverless rewrite rad (DECISION-10).

## Trade-off

Coverage 100%, stale lobby, tarjima review — keyingi DECISION gacha kutadi.

## Ta’sir

- README — freeze eslatmasi
- Yangi feature PR/agent ishi: avval bugfix ekanini tasdiqlash

## Validation (2026-09-22)

| Tekshiruv        | Natija                                      |
| ---------------- | ------------------------------------------- |
| Kod              | faqat hujjat + README                       |
| pytest / qa_gate | **163/163**, **100/100** (DECISION-11 tree) |

**Qolgan risk:** freeze qoidasi buzilsa scope creep.
