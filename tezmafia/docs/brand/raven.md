# Qarg‘a brendi — dizayn tizimi va asset spetsifikatsiyasi

**Holat:** maskot artwork tayyor va botga ulangan (5 bosqich, har biri egasi tomonidan tasdiqlangan).
**Sana:** 2026-10-14
**Mahsulot nomlari o‘zgarmaydi:** bot — `TezMafia`, shahar — `Qorashahar`, username — `@qorashahar_mafia_bot`.

## 1. Qayerda ko‘rinadi (audit natijasi)

Repozitoriyda faqat Telegram bot bor: web sahifa, Mini App, admin panel, CSS yoki komponent kutubxonasi yo‘q.
Bot o‘z interfeysi ranglarini boshqara olmaydi, shuning uchun brend o‘yinchiga quyidagi kanallar orqali yetadi:

| Kanal | Hozir | Kod |
| --- | --- | --- |
| Profil rasmi | `assets/raven/avatar.jpg` | `setup_bot_profile` → `brand.media("avatar")` |
| Faza va hukm rasmlari | 16 ta sahna, `assets/raven/scenes/` | `App.safe_photo` → `brand.MEDIA` |
| Rol kartalari | 21 ta, `assets/raven/roles/` | rol DM'i (`App.dm_photo`), `/roles` kartasi → `brand.role_card` |
| Menyu sarlavhalari | 5 ta, `assets/raven/menu/` | `/start`, `/help`, `/shop`, `/profile`, `/top` → `_answer_with_photo` |
| Bot tavsifi rasmi | `assets/raven/banner.jpg`, 640×360 ga kichraytirib o‘rnatilgan (2026-10-14) | Bot API'da yo‘q — @BotFather → Edit Description Picture |
| Stiker paket | [`raven_by_qorashahar_mafia_bot`](https://t.me/addstickers/raven_by_qorashahar_mafia_bot), 8 ta Qarg‘a; eski `TezMafia_by_menarzullayev` (5 TGS) o‘zgarmagan | `python -m scripts.make_sticker_set` |
| Custom emoji | uchinchi tomon VectorGuard to‘plami | `tezmafia/emoji.py` |
| Tugmalar | Telegram `style` (primary/success/danger) + emoji ikonka | `tezmafia/keyboards.py` |
| Matn | 11 til katalogi | `tezmafia/locales/*.json` |
| Profil matnlari | 11 til | `profile.short`, `profile.desc` |

Eski rasmlar (`avatar.jpg`, `avatar.png`, `day.png`, `night.png`, `death.png`, `mafia-win.png`, `town-win.png`, `phase.gif`, `stickers/icon.png`) va ularni nusxalovchi `scripts/copy_assets.py` egasi roziligi bilan o‘chirildi (2026-10-14); git tarixida qoladi.

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

Hamma fayl `assets/raven/` da; bot faqat `brand.MEDIA` / `brand.role_card` orqali murojaat qiladi.
Manba rasmlar ChatGPT'da chizilgan; kesish va eksport skriptlari `design/raven/stage*/` da (xom PNG'lar gitga kirmaydi).

| Papka / fayl | O‘lcham | Format | Qayerda |
| --- | --- | --- | --- |
| `avatar.jpg` | 640×640 | JPG | profil rasmi (`avatar`) |
| `mark.svg`, `mark-on-dark.svg` | vektor | SVG | kichik belgi (yorug‘ / qorong‘i fon) |
| `logo-{horizontal,stacked}-{dark,light}.svg` | vektor | SVG, shrift yo‘llarga aylantirilgan | logotip: belgi + `TEZMAFIA` (Bahnschrift SemiBold Condensed) |
| `banner.jpg` | 1280×720 | JPG | bot tavsifi rasmi (@BotFather → Edit Description Picture) |
| `scenes/roles-dealt.jpg` | 1280×720 | JPG | `roles_dealt` |
| `scenes/night.jpg` | 1280×720 | JPG | `night` |
| `scenes/dawn.jpg`, `dawn-death.jpg` | 1280×720 | JPG | `dawn`, `dawn_death` (qonsiz, bo‘sh stul) |
| `scenes/trial.jpg` | 1280×720 | JPG | `trial` — ovoz natijasi, hech kim chiqmadi |
| `scenes/verdict-confirm.jpg` | 1280×720 | JPG | `verdict_confirm` — hukmni tasdiqlash (lynch) |
| `scenes/verdict-sealed.jpg` | 1280×720 | JPG | `verdict_sealed` — hukm tasdiqlandi |
| `scenes/win-{mafia,town,maniac,suicide,arsonist,snitch,mage,crook}.jpg` | 1280×720 | JPG | har g‘olibga alohida sahna (`win_media`) |
| `scenes/lobby.jpg` | 1280×720 | JPG | hozircha ishlatilmaydi (pastga qarang) |
| `roles/<role>.jpg` | 640×640 | JPG | 21 rol, `Role` enum qiymati bo‘yicha |
| `menu/h01-start … h05-top.jpg` | 1280×720 | JPG | `menu_start`, `menu_help`, `menu_shop`, `menu_profile`, `menu_top` |
| `stickers/s01-hello … s08-farewell.webp` | 512×512 | WEBP, shaffof | `raven_by_qorashahar_mafia_bot` paketi; emoji `scripts/make_sticker_set.py` da |

Qoidalar: rasmda matn yo‘q; matn caption'da. Caption 1024 belgidan oshsa (`brand.caption_fits`), rasm alohida,
matn alohida xabar bo‘lib ketadi. Rasm yuborilmasa — xabar matn bilan baribir chiqadi; rol DM'ida faqat
yopiq DM (`TelegramForbiddenError`) o‘yinni to‘xtatadi, rasm xatosi emas.

Lobby xabari rasmga aylantirilmadi: u har qo‘shilishda tahrirlanadi va 23 o‘yinchi bilan caption chegarasidan
oshishi mumkin. Ovoz xabari ham shu sababli matnligicha qoldi.

## 7. Ovoz

Matnlar 2026-10-13/14 da egasi tomonidan qatorma-qator tanlangan va brend ovoziga (qisqa, quruq, sirli) mos.
Qarg‘ani hikoyachi qilib matnlarga kiritish — alohida qaror; egasining roziligisiz matnlar o‘zgartirilmaydi.

## 8. Migratsiya cheklisti

- [x] Audit (1–2-bo‘lim)
- [x] Tokenlar va kontrast (`brand.PALETTE`)
- [x] Media xaritasi: `bot.py` dagi qattiq yozilgan rasm nomlari → `brand.MEDIA`, testlar (`tests/test_brand.py`)
- [x] Maskot referensi: 15 variantli konsepsiya varag‘i (`design/raven/concept-sheet-15.png`)
- [x] 1-bosqich: avatar + belgi (SVG)
- [x] 2-bosqich: banner + logotip
- [x] 3-bosqich: 16 ta o‘yin sahnasi
- [x] 4-bosqich: 21 ta rol kartasi
- [x] 5-bosqich: 5 ta menyu sarlavhasi + 8 ta stiker
- [x] `MEDIA` almashtirish, rol kartalari, menyu sarlavhalari, testlar (`tests/test_brand.py`, `tests/test_raven_media.py`)
- [x] Bot tavsifi rasmi — @BotFather orqali o‘rnatildi
- [x] Stiker paketi `raven_by_qorashahar_mafia_bot` (8 ta)
- [ ] Custom emoji: brendga mos to‘plam tanlash (yangi ID'lar o‘ylab topilmaydi)
- [x] Eski rasmlarni o‘chirish (1-bo‘lim)
