# DECISION-07 — Competitor E2E maqsad yopiladi

**Status:** accepted  
**Date:** 2026-09-21  
**Decider:** user (AskUserQuestion `e2e-after-i18n`)  
**Depends on:** DECISION-04, DECISION-05, DECISION-06

## Qaror

Variant **A — Maqsadni yopish.** Katalog + live EN `/roles` yetarli.

Yopilish bar (o‘lchangan):

1. Live 5p uz: ticket, loadout, N1 no-shoot, last-words, unmute (DECISION-04).
2. Host UX: 11 til picker + `/chats`/`/enter` (DECISION-05).
3. Gameplay i18n: 11×21 + fazalar; live EN `/roles`/`/start`/`/settings` (DECISION-06).
4. Donate/IAP klon qilinmagan.

## Sabab

C i18n qatlami o‘lchangan. Qo‘shimcha EN 5p yoki 11 til human-review yangi arxitektura emas — content/QA dasturi.

## Trade-off

Live rol DM non-uz da qayta o‘ynalmagan. kz/kg/tj tarjima review yo‘q. Goal yopilishi shu risklarni yo‘qotmaydi, faqat E2E scope ni to‘xtatadi.

## Ta’sir

- `docs/competitor-matrix.md` — E2E bar **closed**
- Cursor goal → complete
