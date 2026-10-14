# DECISION-17 — O‘sish, bot-o‘yinchilar va daromad (H1–H4)

**Status:** accepted  
**Date:** 2026-10-15  
**Decider:** user (AskUserQuestion, 4 bosqich)  
**Depends on:** DECISION-16, docs/LOADTEST.md

## Qarorlar

| Mavzu | Qaror |
| --- | --- |
| O‘sish kanallari | Yangiliklar kanali + avto-post, guruh admini mukofoti, kataloglar (Apps Center, tgstat va b.), Telegram Ads |
| Kanal | "TezMafia — Qorashahar" (id `-1004236546637`), username `@tezmafia` — egasi o‘rnatadi; bot admin |
| Kanal posti | Faqat haftalik (dushanba): turnir g‘oliblari, klan reytingi, hafta raqamlari |
| Admin mukofoti | Botni qo‘shgan admin guruhda 5+ odamli birinchi o‘yin o‘tsa: 200 coin + 2 olmos + 🎖 "Asoschi"; har guruh uchun bir marta, bitta admin ko‘pi bilan 5 guruh |
| Analitika | Funnel (bot qo‘shildi → lobby → boshlandi → tugadi → qayta o‘ynadi) + har dushanba egasiga hisobot + Mini App'da faqat egaga admin sahifasi |
| 5 kishi to‘sig‘i | Bot-o‘yinchilar bo‘sh o‘rinlarni to‘ldiradi, cheklovsiz (1 odam + botlar — mashq) |
| Botli o‘yin mukofoti | 5+ odam: to‘liq; 3–4 odam: XP va coin yarmi, turnir/reyting ochkosi yo‘q; 1–2 odam: faqat XP |
| Mavsumiy pass | 99 ⭐/oy, 20 bosqich (bepul + pullik yo‘lak), 1-noyabrdan |
| Rol skinlari | Avval mavjud kartalardan 3 avtomatik uslub (Noir, Oltin, Neon), keyin AI-art; har uslub 20 olmos, passning pullik yo‘lagida 1 uslub bepul |
| Guruh premium | 199 ⭐/oy: uzun vaqtlar, maxsus rollar to‘plamini saqlash, guruh nomi kartada, kengaytirilgan /groupstats |
| Reklama materiallari | O‘zbek + rus |

## Tartib

1. **H1 O‘sish:** kanal + haftalik post, admin mukofoti, funnel va haftalik hisobot.
2. **H2 Bot-o‘yinchilar** (mukofot odam soniga qarab).
3. **H3 Daromad:** pass (1-noyabr), skinlar, guruh premium.
4. **H4 Katalog va reklama materiallari** (uz + ru).

Har bosqich alohida PR → CI → merge → deploy → production'da o‘lchash.

## Avvalgi sessiyadagi qarorlar (2026-10-15)

- 5 ta haqiqiy hisobga soxta o‘yinlardan mos yutuqlar berildi (hisoblar qoldi).
- W42 turnir sovrini o‘z holicha (soxta o‘yinchilar ham olishi mumkin).
- Baza zaxirasi kerak emas.
- Durang: 3 aylanma o‘limsiz va ≤4 tirik.
