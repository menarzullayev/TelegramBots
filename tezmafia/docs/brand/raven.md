# Qarg‘a brendi — dizayn tizimi va asset spetsifikatsiyasi

**Holat:** poydevor tayyor (kod + tokenlar); maskot artwork kutilmoqda.
**Sana:** 2026-10-14
**Mahsulot nomlari o‘zgarmaydi:** bot — `TezMafia`, shahar — `Qorashahar`, username — `@qorashahar_mafia_bot`.

## 1. Qayerda ko‘rinadi (audit natijasi)

Repozitoriyda faqat Telegram bot bor: web sahifa, Mini App, admin panel, CSS yoki komponent kutubxonasi yo‘q.
Bot o‘z interfeysi ranglarini boshqara olmaydi, shuning uchun brend o‘yinchiga quyidagi kanallar orqali yetadi:

| Kanal | Hozir | Kod |
| --- | --- | --- |
| Profil rasmi | `assets/avatar.jpg` (fedora + qizil ko‘z) | `setup_bot_profile` → `brand.media("avatar")` |
| Faza rasmlari | 5 ta raster: `day`, `night`, `death`, `mafia-win`, `town-win` | `App.safe_photo` → `brand.MEDIA` |
| Bot tavsifi rasmi (1280×720) | o‘rnatilmagan | Bot API'da yo‘q — faqat @BotFather orqali qo‘lda |
| Stiker paket | `TezMafia_by_menarzullayev`, 5 ta oddiy TGS | `scripts/make_tgs.py` (yuklash qo‘lda) |
| Custom emoji | uchinchi tomon VectorGuard to‘plami | `tezmafia/emoji.py` |
| Tugmalar | Telegram `style` (primary/success/danger) + emoji ikonka | `tezmafia/keyboards.py` |
| Matn | 11 til katalogi | `tezmafia/locales/*.json` |
| Profil matnlari | 11 til | `profile.short`, `profile.desc` |

Ishlatilmaydigan fayllar: `assets/phase.gif`, `assets/avatar.png`, `assets/stickers/icon.png` — kod ularga murojaat qilmaydi.

## 2. Brend nomuvofiqliklari (hozirgi holat)

1. Avatar — mafia janrining eng keng tarqalgan klishesi (fedora, qizil ko‘z, oltin skyline); 40 px da skyline yo‘qoladi.
2. Faza rasmlari — Yevropa shahrining fotorealistik rasmlari; avatar bilan uslub va palitra umumiy emas.
3. Stikerlar — rangli aylana/kvadrat animatsiyalar, brend belgisi yo‘q.
4. `emoji.py` da 6 ta slot boshqa slot ID'sini qayta ishlatadi: `night`=`hourglass`, `day`=`star`, `death`=`cross`, `mafia`=`lock`, `town`=`shield`, `vote`=`bolt`. Ya’ni “tun” xabarida qum soati, “o‘lim”da ✖ chiqadi.
5. Rasm nomlari `bot.py` ichida tarqalgan edi — endi `brand.MEDIA` da (bu PR).

## 3. Tokenlar

Manba: `tezmafia/brand.py` (`PALETTE`). Kontrast — WCAG, `raven_black` fonda o‘lchangan:

| Token | HEX | Vazifa | Kontrast |
| --- | --- | --- | --- |
| `raven_black` | `#101116` | asosiy fon, qarg‘a pati | — |
| `charcoal` | `#1A1C23` | ikkinchi sirt, kartochka | — |
| `burgundy` | `#721F2B` | sharf, sirt (ustida faqat `ivory`) | 1.75 · ivory ustida 8.95 |
| `raven_red` | `#C83D46` | aksent: belgilar, katta yozuv | 3.78 — mayda matnga yaramaydi |
| `red_text` | `#D9545C` | qizil mayda matn kerak bo‘lsa | 4.82 |
| `gold` | `#C5A15A` | medalyon, ingichka chiziq, sarlavha | 7.74 |
| `ivory` | `#F1E9DB` | asosiy matn, yorug‘ fon varianti | 15.64 |
| `ash` | `#9A958C` | ikkinchi darajali matn | 6.33 |

Qoidalar: aksent (`raven_red`, `gold`) bitta kompozitsiyada bittadan ortiq katta maydonni egallamaydi; qizil — xavf/o‘lim/Mafiya, oltin — hukm, medalyon, g‘alaba.

## 4. Tipografiya (rasm ichidagi)

Telegram matni foydalanuvchi shriftida chiqadi, shuning uchun shrift faqat rasm va logotipga tegishli.
- Wordmark: qo‘lda chizilgan yoki litsenziyali serif/display; `TezMafia` aynan shu yozilishda.
- Rasm ichida lokalizatsiya qilinadigan matn **bo‘lmaydi**: faza nomi, g‘olib, shiorlar — xabar matnida (`locales/*.json`), rasmda emas.

## 5. Maskot qoidalari

Xarakter: aqlli, sirli, kuzatuvchan, hukm chiqaruvchi. Belgilar: qora pat, to‘q qizil sharf, soddalashtirilgan shahar motivli oltin medalyon.

| Variant | Qachon | Talab |
| --- | --- | --- |
| To‘liq illyustratsiya | banner, g‘alaba rasmlari | sharf va medalyon ko‘rinadi |
| Ixcham avatar | Telegram profil rasmi | doira ichida bosh + sharf; 40 px da siluet tanilsin; medalyon detali soddalashtiriladi |
| Kichik belgi (mark) | stiker ikonkasi, favicon, 20–32 px | 2–3 rang yoki bir rang; ichki detal yo‘q |
| Monoxrom | muhr, bir rangli fon | faqat siluet + sharf shakli |

Taqiqlar: fedora, plash, qurol, qon, katta yonib turgan ko‘zlar, doira ichidagi umumiy shahar, karta mastlari. Qarg‘a bolalarcha/kulgili ifodada chizilmaydi.

## 6. Asset spetsifikatsiyasi

Yangi fayllar `assets/raven/` ga tushadi; tayyor bo‘lgach faqat `brand.MEDIA` qiymatlari almashadi.

| Fayl | O‘lcham | Format | `MEDIA` kaliti | Mazmun |
| --- | --- | --- | --- | --- |
| `raven/avatar.jpg` | 640×640 | JPG ≤ 500 KB | `avatar` | ixcham avatar, to‘liq fon (Telegram doiraga kesadi) |
| `raven/mark.svg` | vektor | SVG, shaffof | — | kichik belgi |
| `raven/logo.svg` | vektor | SVG | — | belgi + `TezMafia` wordmark |
| `raven/banner.jpg` | 1280×720 | JPG | — | bot tavsifi rasmi (@BotFather → Edit Description Picture) |
| `raven/roles.jpg` | 1280×720 | JPG | `roles_dealt` | qarg‘a konvertlarni tarqatadi |
| `raven/night.jpg` | 1280×720 | JPG | `night` | tun, qarg‘a tomda kuzatadi |
| `raven/dawn.jpg` | 1280×720 | JPG | `dawn` | tong, tinch |
| `raven/dawn-death.jpg` | 1280×720 | JPG | `dawn_death` | tong, qurbon bor (qon va jasadsiz) |
| `raven/win-mafia.jpg` | 1280×720 | JPG | `win_mafia` | qizil hukmronlik |
| `raven/win-town.jpg` | 1280×720 | JPG | `win_town` | oltin, adolat |
| `raven/win-solo.jpg` | 1280×720 | JPG | `win_solo` | yolg‘iz g‘olib (Manyak, Arsonist…) |

Barchasi: rasmda matn yo‘q, asosiy obyekt markaziy 60% ichida (Telegram ko‘rinishda kesadi), bitta palitra (3-bo‘lim).

## 7. Ovoz

Matnlar 2026-10-13/14 da egasi tomonidan qatorma-qator tanlangan va brend ovoziga (qisqa, quruq, sirli) mos.
Qarg‘ani hikoyachi qilib matnlarga kiritish — alohida qaror; egasining roziligisiz matnlar o‘zgartirilmaydi.

## 8. Migratsiya cheklisti

- [x] Audit (1–2-bo‘lim)
- [x] Tokenlar va kontrast (`brand.PALETTE`)
- [x] Media xaritasi: `bot.py` dagi qattiq yozilgan rasm nomlari → `brand.MEDIA`, testlar (`tests/test_brand.py`)
- [ ] Maskot referensi (tanlangan qarg‘a konsepsiyasi) — **kutilmoqda**
- [ ] `assets/raven/*` (6-bo‘lim) va `MEDIA` almashtirish
- [ ] Bot tavsifi rasmi — @BotFather orqali qo‘lda
- [ ] Stiker paket va custom emoji: brendga mos to‘plam tanlash (yangi ID'lar o‘ylab topilmaydi)
