# DECISION-15 — Jahon standarti va Bot API 10.3 ga modernizatsiya

**Status:** accepted  
**Date:** 2026-10-14  
**Decider:** user  
**Supersedes:** DECISION-13 (feature freeze)  
**Depends on:** DECISION-01, DECISION-10

## Qaror

TezMafia bosqichma-bosqich modernizatsiya qilinadi. To‘liq reja: `docs/roadmap-2026-modernization.md`.
Egasi tomonidan `AskUserQuestion` orqali qabul qilingan qarorlar:

| Mavzu | Qaror |
| --- | --- |
| Qamrov | Hamma yo‘nalish; tartib: avval asos (ishonchlilik, xavfsizlik), keyin qoidalar, Bot API, o‘yin |
| Production | Hozircha shu PC: Windows'da avto-start; PC Linux'dan yuklansa bot Linux'da avtomatik ishga tushadi. Serverga ko‘chish — 1000+ foydalanuvchidan keyin |
| Baza | Ikkala OS bitta bazani ishlatadi: `D:\Linux\TelegramBots\tezmafia\data` (Windows Fast Startup o‘chiq bo‘lishi shart) |
| Rol oqimi | DM asosiy (MAU kafolatli); ephemeral xabarlar faqat qo‘shimcha qulaylik. Bot o‘z MAU analitikasini yuritadi |
| Monetizatsiya | Stars (`XTR`): 4 ta bonusli coin paketi + oylik VIP obuna |
| Olmos | Faqat kosmetika valyutasi (o‘yinga ta’sir qilmaydi) |
| O‘yin | `/config` panel, rejimlar, yutuqlar va daraja, mavsumiy reyting + so‘nggi so‘z + o‘yin tarixi |
| Hujjatlar | `/privacy`, `/terms`, `/paysupport` bot ichida 11 tilda + to‘liq matn telegra.ph'da |
| Mini App | Asosiy bosqichlardan keyin |
| Monitoring | Xato va holat ogohlantirishlari egasiga Telegram DM orqali + kunlik hisobot |

## Sabab

- Audit (2026-10-14): o‘yin qotib qolishi, global lock, huquq tekshiruvlaridagi bo‘shliqlar, `/privacy` yo‘qligi.
- Telegram Developer ToS: raqamli tovar faqat Stars bilan; `/paysupport`, `/terms`, privacy policy majburiy.
- Bot API 10.3 (2026-08-24) imkoniyatlari ishlatilmagan; aiogram 3.31 ularni to‘liq qo‘llaydi.

## Ochiq savollar

- Telegram bot MAU'sini qanday hisoblashi rasmiy e’lon qilinmagan; ephemeral bosish MAU'ga kirishi tajriba bilan tekshiriladi.
- Linux tomonidagi repo yo‘li va D: disk mount nuqtasi Linux'ga birinchi yuklanishda aniqlanadi.
