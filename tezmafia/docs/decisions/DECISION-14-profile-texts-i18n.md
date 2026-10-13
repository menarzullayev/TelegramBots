# DECISION-14 — Bot profil matnlari 11 tilda

**Status:** accepted  
**Date:** 2026-10-14  
**Decider:** user  
**Supersedes:** DECISION-12  
**Depends on:** DECISION-06, DECISION-09

## Qaror

Short description va description har til uchun alohida o‘rnatiladi (`setMyShortDescription` /
`setMyDescription` + `language_code`). Standart (tilsiz) variant — uz.

Menyu buyruqlari tavsifi (`cmd.*`) va profil matnlari (`profile.short`, `profile.desc`) endi
`locales/*.json` katalogida; `i18n.py` dagi alohida `_CMD` lug‘ati olib tashlandi.

## Sabab

uz matnlar to‘liq qayta yozilgach (PR #3) boshqa tillar ham shu manbadan tarjima qilindi. Bot
kartochkasi yagona tarjimasiz joy bo‘lib qoldi: EN foydalanuvchi o‘yinni inglizcha, kartochkani
esa o‘zbekcha ko‘rardi (DECISION-12 dagi “qolgan risk”).

## DECISION-12 dagi to‘siqlar qanday yopildi

| To‘siq (2026-09-22)   | Yechim                                                                     |
| --------------------- | -------------------------------------------------------------------------- |
| SetMyName flood       | Nom faqat birinchi marta o‘rnatiladi (oldingi `.profile_*` marker bo‘lmasa) |
| Ko‘p tilli API xarajat | `data/.profile_<digest>`: so‘rovlar faqat katalog matni o‘zgarganda ketadi  |
| Flood o‘rtada uzilsa   | Marker yozilmaydi — keyingi startda qayta uriniladi                         |

## Trade-off

Matn o‘zgargan startda 22 ta qo‘shimcha Bot API so‘rovi (11 til × 2). Odatdagi startda 0.

## DECISION-13 (freeze) bilan munosabati

Yangi product scope emas: mavjud matnlarning tarjima bo‘shlig‘ini yopadi. Foydalanuvchi so‘rovi
bilan qilindi.

## Ta’sir

- `tezmafia/bot.py` — `_sync_bot_profile`, `setup_bot_profile`
- `tezmafia/i18n.py` — `cmd()` katalogdan o‘qiydi
- `tezmafia/locales/*.json` — `cmd.*` (17) va `profile.*` (2) kalitlari

## Validation (2026-10-14)

| Tekshiruv | Natija                                                                    |
| --------- | ------------------------------------------------------------------------- |
| pytest    | profil sync: flood, legacy marker, idempotentlik; Telegram uzunlik limitlari |
| qa_gate   | **100/100**                                                               |

**Qolgan risk:** tarjimalarni ona tili egasi ko‘rib chiqmagan.
