# DECISION-18 — Telegram kanalini noldan yuritish

**Status:** accepted (prototip bosqichi)  
**Date:** 2026-10-15  
**Decider:** user (AskUserQuestion, 3 bosqich)  
**Depends on:** DECISION-17

## Tadqiqot (2026-10-15, manbalar bilan)

- Telegram 2026 (aprel–avgust): Communities, Welcome Messages, xabar ichida ko‘p tugma (Bot API 10.3),
  Mighty Polls, poll cheklovlari (faqat obunachilar / mamlakat), karusel postlar, rich message kanallarda.
- Bot kanal uchun: post/tahrir/pin, rich bloklar (details, slideshow, table, buttons), poll/quiz, obunani
  tekshirish, Stars obuna havolasi. Qila olmaydi: story, statistika, Telegram ichida rejalash, 48 soatdan
  eski postni o‘chirish, message effects.
- Yuritish: reach 2025-dan beri ~53% tushgan; kuniga ≤1–2 post; reklamadan oldin 10–15 post; eng arzon
  o‘sish — botning o‘z foydalanuvchilari; Telegram Ads faqat 1000+ obunachili kanallarda ko‘rinadi.

## Qarorlar

| Mavzu | Qaror |
| --- | --- |
| Til | Bitta kanal, asosiy o‘zbekcha; ruscha va inglizcha yig‘ma (details) bo‘limlarda, rich message |
| Tuzilma | Kanal + "TezMafia chat" muhokama guruhi + Community (ulash egasi tomonidan ilovada) |
| Chastota | Hozircha butun loyiha imkoniyatlari seriyasi; haftalik chastota keyin |
| Vaqt | 20:00 (Toshkent) + 2 haftalik A/B |
| Seriya | GitHub tarixidan 63 post (`channel/inventory.md`), avval yopiq "TezMafia drafts" kanalida prototip |
| Ma’lumot | Soxta (yuklama sinovi) ma’lumot production oldidan tozalanadi; postlarda haqiqatga yaqin namunalar |
| Muallif | Bot (rich message bloklari) |
| Vizual | Agent tayyorlaydi (Pillow chat mock-up, mavjud Raven rasmlari; kerak bo‘lsa AI generatsiya), egasi tanlaydi |
| Da’vo | "Stars faqat kosmetika" noto‘g‘ri — tuzatildi: olmos/skin/belgi/pass kosmetik, coin o‘yin buyumlariga ham ketadi |
| Avto-dayjest | `NEWS_CHANNEL` soxta ma’lumot tozalanguncha o‘chiq |

## Vositalar

- `channel/posts/*.json` — 63 post (uz/ru/en), `channel/README.md` — sxema va yozish qoidalari.
- `scripts/channel_mock.py` — Raven uslubidagi chat mock-up (rangli emoji bilan).
- `scripts/channel_publish.py` — rich message yuborish/joyida tahrirlash, file_id keshi, flood-wait, poll.
