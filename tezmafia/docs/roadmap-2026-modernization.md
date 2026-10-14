# TezMafia modernizatsiya yo‘l xaritasi (2026-10)

Qarorlar: `docs/decisions/DECISION-15-modernization-2026.md`. Har bosqich — alohida PR, CI yashil bo‘lgach merge va
production'da o‘lchash. Bosqich ichidagi kattaroq tanlovlar egasi bilan `AskUserQuestion` orqali kelishiladi.

## F0 — Ishga tushirish va kuzatuv
- Windows: Task Scheduler orqali login/boot'da avto-start, qulasa qayta ishga tushish, bitta nusxa kafolati.
- Linux (dual-boot): systemd user service, D: diskdagi umumiy `data/`; ma’lumot yo‘llari absolyut (`DATA_DIR`).
- Egasiga Telegram ogohlantirishlari: xato, qotib qolgan o‘yin, flood-limit, qayta ishga tushish; kunlik hisobot.

## F1 — Asos: ishonchlilik va xavfsizlik
- Har chat uchun alohida lock; Telegram so‘rovlari lock'dan tashqarida.
- Faza o‘tishida taymer har doim qo‘yiladi (`try/finally`); `TelegramRetryAfter` hurmat qilinadi.
- Umumiy xato handler'i, callback ma’lumotini tekshirish, throttling middleware.
- Huquqlar: `/extend` faqat host, guruh tili faqat admin, faqat guruh a’zolari qo‘shiladi.
- Xatolar: `dm_pending` xom matni, lobby unpin, profil rasmi marker'i, `/next` lock'i, `ROLE_ASSIGNMENT` tiklanishi,
  ovoz jadvalida mer/firibgar vazni.
- SQLite WAL, eski o‘yinlarni tozalash, `aiogram>=3.31` pin, ruff + mypy CI'da.
- Guruh limiti (20 xabar/daqiqa): faza xabarlarini birlashtirish.

## F2 — Telegram qoidalari
- `/privacy`, `/terms`, `/paysupport` 11 tilda + telegra.ph sahifalari, BotFather'da privacy havolasi.
- `/deletemydata`: foydalanuvchi ma’lumotini o‘chirish; o‘yin tarixini saqlash muddati.

## F3 — Bot API 10.3
- Ephemeral qo‘shimchalar (DM o‘rnini bosmaydi): "rolimni eslat", ovoz tasdig‘i.
- O‘lgan o‘yinchi tugmalari `disabled`; o‘yin yakuni rich message jadvali; `date_time` taymerlar.
- `my_chat_member` / `chat_member`: guruhga qo‘shilganda salomlashish, chiqarilganda tozalash.
- MAU analitikasi: oyiga noyob foydalanuvchilar DM / guruh / ephemeral bo‘yicha.

## F4 — Iqtisod (Stars)
- 4 ta coin paketi: 25⭐→100 · 100⭐→450 · 250⭐→1200 · 500⭐→2600.
- Oylik VIP obuna (Stars subscription, 30 kun).
- To‘lovlar jurnali (`telegram_payment_charge_id`), refund, `/paysupport` oqimi.
- Olmos — kosmetika do‘koni (ramka, nishon).

## F5 — O‘yin
- `/config` guruh paneli: taymerlar, rol to‘plami, rolni ochish/yashirish, mute, til.
- Rejimlar: Classic, Chaos, Secret, Tezkor.
- Yutuqlar, XP va daraja.
- Mavsumiy va guruh reytingi, so‘nggi so‘z, o‘yin tarixi.

## F6 — Mini App
- Profil, yutuqlar, reyting, do‘kon, qoidalar; emoji status (ruxsat Mini App orqali).

## F7 — Serverga ko‘chish
- 1000+ foydalanuvchidan keyin: Linux VPS, avto-deploy (`tezmafia-deploy.yml`), keyin Postgres/Redis.
