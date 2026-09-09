# TezMath — TOP 50 Tavsiyalar

ROADMAP.md da belgilangan vazifalardan tashqari loyihani professional darajaga olib chiqish uchun quyidagi tavsiyalar.

---

## 🔐 Xavfsizlik (Security)

**1. Bot token va API kalitlarni rotate qilish tizimi**
Barcha tokenlar (BOT_TOKEN, ANTHROPIC_API_KEY, PAYME_SECRET) ma'lum vaqt oralig'ida avtomatik almashtirilishi kerak. HashiCorp Vault yoki AWS Secrets Manager ishlatish.

**2. SQL injection himoyasi auditi**
Hozir `asyncpg` parametrli so'rovlar ishlatadi — bu yaxshi. Lekin SQLite da string interpolatsiya qilib qo'yilgan joylar bor. Barcha DB so'rovlari `?` yoki `$N` bilan yozilganligini tekshirish.

**3. Telegram webhook signature tekshirish**
Webhook rejimida Telegram dan kelgan so'rovlarning `X-Telegram-Bot-Api-Secret-Token` headerini tekshiruvchi middleware qo'shish. Hozir `webhook_secret` faqat o'rnatiladi lekin tekshirilmaydi.

**4. Rate limiting IP darajasida**
Foydalanuvchi rate limit faqat `telegram_id` bo'yicha. Bir IP dan ko'p akkaunt yaratib aylanib o'tish mumkin. nginx da `limit_req_zone $binary_remote_addr` allaqachon bor — buni bot darajasida ham qo'llash.

**5. Admin buyruqlarida ikkinchi tasdiqlash**
`/ban`, `/broadcast` kabi xavfli buyruqlarga `Are you sure? Reply /confirm` shaklidagi tasdiqlash qadami qo'shish.

**6. Foydalanuvchi kiritgan matnni sanitize qilish**
Telegram xabardagi matn to'g'ridan Claude ga uzatiladi. Prompt injection hujumidan himoyalanish uchun kiruvchi matnni filterlash qatlami qo'shish.

**7. Payme secret key HMAC tekshiruvi**
Payme webhook da Base64 decode + password taqqoslash bor. Lekin constant-time comparison (`hmac.compare_digest`) ishlatilmagan — timing attack mumkin. `secrets.compare_digest` ga o'tkazish.

**8. CORS white-list**
Admin panel da hozir `allow_origins=["http://localhost:3000"]`. Production da real domain qo'yish va `allow_credentials=True` bilan birga wildcard ishlatmaslik.

**9. JWT expiry va refresh token**
Admin panel JWT `exp: now + 86400` (1 kun). Qisqaroq `access_token` (15 daqiqa) + `refresh_token` (30 kun) sxemasiga o'tish.

**10. Foydalanuvchi ma'lumotlarini shifrlash**
Bazada `full_name`, `username` ochiq saqlanadi. GDPR talablariga ko'ra foydalanuvchi o'chirish so'raganda barcha ma'lumotlarni tozalash funksiyasi kerak (`/deleteaccount` buyrug'i).

---

## ⚡ Ishlash tezligi (Performance)

**11. Connection pooling sozlash**
`asyncpg` pool `min_size=2, max_size=10`. Yuklanish testidan so'ng optimal qiymatni topish. Har bir so'rov uchun yangi ulanish ochilmasligi kerak.

**12. Redis caching — foydalanuvchi ma'lumotlari**
Har bir xabarda `get_or_create_user()` DB ga so'rov yuboradi. Foydalanuvchi obyektini Redis da 5 daqiqa cache qilish — DB yukini 80% kamaytiradi.

**13. Claude API streaming**
Hozir `messages.create()` to'liq javobni kutadi (10-30 soniya). `stream=True` bilan javobni qismlarga bo'lib "⏳ yechilmoqda... (1/3)" shaklida yuborish — UX sezilarli yaxshilanadi.

**14. Rasm kompressiya**
`photo_handler` da Telegram fotosuratini to'liq baytda Claude ga yuboradi. `Pillow` bilan oldindan kichraytirish (max 1024px, JPEG 85%) — API xarajatini kamaytiradi.

**15. Async batch operations**
Broadcast da `asyncio.gather()` bilan 25 ta xabar parallel yuboriladi — bu yaxshi. Lekin DB so'rovlari hali ham ketma-ket. `asyncpg` `executemany()` ishlatish.

**16. CDN rasm saqlash**
MinIO/S3 da saqlangan render PNG larni Cloudflare CDN orqali uzatish — Telegram ga rasm yuborish tezlashadi.

**17. Lazy import optimallashtirish**
`handlers/callbacks/menu_callback.py` da har callback bosilganda `from handlers.commands.profile import profile_handler` import qilinadi. Modullarni top-level import qilish.

**18. Database index qo'shish**
`solutions` jadvalida `(user_id, created_at)` composite index yo'q. 1 million yozuvdan keyin `get_solution_history()` sekinlashadi. Migration da qo'shish.

**19. Webhook vs Polling**
Polling har 5 soniyada Telegram serveriga so'rov yuboradi. Production da webhook rejimiga o'tish — server yukini 90% kamaytiradi va latencyni 5s dan <1s ga tushiradi.

**20. Task queue prioriteti**
Premium foydalanuvchilar xabarlari bepul foydalanuvchilardan oldin yechilishi kerak. RabbitMQ da `priority queue` sozlash (0-10 daraja).

---

## 🎨 Foydalanuvchi tajribasi (UX)

**21. Typing indicator**
Masala qayta ishlayotganda `await context.bot.send_chat_action(chat_id, "typing")` yuborish — foydalanuvchi bot ishlayotganini ko'radi.

**22. Yechim formatlash**
Claude markdown qaytaradi, lekin Telegram `parse_mode="Markdown"` da ba'zi belgilar (`_`, `*`, `` ` ``) muammo chiqaradi. `MarkdownV2` ga o'tish yoki HTML parse mode ishlatish.

**23. Xato xabarlarini lokalizatsiya qilish**
Hozir ba'zi xatolar inglizcha chiqadi (`"⛔ Access denied."`). Barcha xabarlar `i18n.py` dan olish.

**24. Onboarding flow**
Yangi foydalanuvchi `/start` bosganida faqat menyu ko'rsatiladi. 3 bosqichli onboarding: "1️⃣ Masala yozing → 2️⃣ Javob oling → 3️⃣ Bahoyig'i" animatsiyali ko'rsatish.

**25. Yechim tarixida pagination**
`/history` faqat oxirgi 5 ta ko'rsatadi. `◀ Oldingi | Keyingi ▶` tugmali pagination qo'shish (Inline keyboard + offset).

**26. Masalani qayta yuborish tugmasi**
Har bir yechim ostiga `🔄 Qayta yechish` tugmasi qo'shish — foydalanuvchi boshqa usul bilan yechim so'rashi mumkin.

**27. Yechim ulashish**
`📤 Ulashish` tugmasi: `t.me/share/url?url=...` orqali yechimni do'stlarga yuborish imkoniyati.

**28. Til tanlash /start da**
Yangi foydalanuvchi `/start` bosganida darhol til tanlash klaviaturasi chiqishi kerak, keyin welcome xabar.

**29. Premium tugash ogohlantirishni oldindan yuborish**
Obuna tugashiga 3 kun qolganda foydalanuvchiga eslatma yuborish scheduler orqali.

**30. Statistika grafiği**
`/profile` da foydalanuvchining haftalik faoliyatini ASCII bar chart ko'rinishida ko'rsatish.

---

## 💰 Biznes logikasi (Business)

**31. Freemium limitini konfiguratsiya qilish**
Hozir `FREE_DAILY_LIMIT=5` hardcoded `.env` da. Admin panel dan dinamik o'zgartirish imkoniyati kerak (Redis da saqlash).

**32. Referral darajali tizim**
Hozir referral faqat kimni taklif qilganini saqlaydi. Darajali mukofot: 1 ta taklif = +1 kun premium, 5 ta = +1 hafta, 10 ta = +1 oy.

**33. Promokod tizimi**
`/promo TEZMATH30` buyrug'i: bazada promokodlar jadvali, bir martalik yoki muddatli chegirmalar.

**34. Yillik obuna**
Hozir faqat oylik (30,000 UZS). Yillik narx (250,000 UZS — 2 oy bepul) qo'shish: yuqori LTV.

**35. Korporativ tarif**
Maktablar va o'quv markazlari uchun ko'p foydalanuvchili litsenziya (narx kelishilgan, admin dashboard).

**36. Affiliate tizimi**
Telegram kanallari va blogerlar uchun ref link + komissiya (har Premium sotuvdan %). Alohida affiliate dashboard.

**37. To'lov tarixini eksport qilish**
Foydalanuvchi `/transactions` buyrug'i bilan o'z to'lov tarixini CSV/PDF shaklida yuklashi.

**38. Qaytarim (Refund) tizimi**
Payme/Click orqali to'lov 24 soat ichida bekor qilinishi mumkin bo'lsin. Admin dan manual refund buyrug'i.

**39. A/B test — onboarding**
Yangi foydalanuvchilar 2 guruhga bo'linib turli onboarding oqimlarini sinash. Qaysi biri ko'proq premium sotishi aniqlanadi.

**40. Push notification — qaytish**
3 kun faol bo'lmagan foydalanuvchiga "Matematika masalangiznomi bormi? 🤔" shaklidagi re-engagement xabari.

---

## 🛠 DevOps va Infratuzilma

**41. Zero-downtime deployment**
Hozir `docker compose up -d` eski container o'chib yangi ko'tarilguncha bot ishlamaydi. Blue-green deployment yoki rolling update sozlash.

**42. Avtomatik SSL yangilash**
`certbot renew` cronjob allaqachon qo'yilishi kerak. Let's Encrypt sertifikati 90 kunda tugaydi — GitHub Actions da avtomatlashtirish.

**43. Database backup avtomatlashtirish**
Kunlik `pg_dump` → S3/MinIO ga yuklash + eski backuplarni 30 kundan keyin o'chirish. `Makefile` da `make backup` allaqachon bor — cron ga qo'yish.

**44. Health check endpoint**
Barcha servislarda `/health` bor. Lekin chuqurroq `/health/ready` (DB + Redis + RabbitMQ ulanganligini tekshiradi) va `/health/live` (process tirik) ajratish.

**45. Sentry error tracking**
`sentry_dsn` konfiguratsiyada bor lekin `sentry_sdk.init()` hech qayerda chaqirilmagan. Bot-gateway va ai-solver da Sentry ulash — real vaqtda xatolar monitoring.

**46. Docker image hajmini kamaytirish**
Hozirgi `python:3.12-slim` ~150MB. Multi-stage build ishlatish: build stage da dependencies o'rnatib, runtime stage da faqat zaruriylarni qoldirish → ~80MB.

**47. Kubernetes manifest**
Katta yuklanishda Docker Compose yetarli emas. `k8s/` papkasida Deployment, Service, HPA (HorizontalPodAutoscaler) manifestlari tayyorlash.

**48. Secrets management**
`.env` fayllari git da yo'q — yaxshi. Lekin CI/CD da `secrets.PROD_HOST` kabi GitHub Secrets ishlatilmoqda. Vault yoki Doppler ga o'tish — rotatsiya osonlashadi.

**49. Canary deployment**
Yangi versiyani avval 10% foydalanuvchilarga chiqarish, xato ko'rsatkichi normal bo'lsa 100% ga kengaytirish. nginx `split_clients` yoki Kubernetes traffic splitting.

**50. Cost monitoring**
Anthropic API xarajati nazorat qilinmaydi. Prometheus da `tokens_used` metrikasini kuzatish + oylik limit (`MAX_MONTHLY_TOKENS`) yetganda premium foydalanuvchilarga ham limit qo'yish va admin ga xabar yuborish.

---

## Ustuvorlik matritsasi

| Daraja | Raqamlar | Tavsif |
|---|---|---|
| 🔴 Darhol | 3, 7, 13, 21, 22, 45 | Xavfsizlik va UX uchun kritik |
| 🟡 Qisqa muddatli (1 oy) | 2, 12, 14, 24, 25, 29, 31, 43 | Biznes va ishlash tezligi |
| 🟢 O'rta muddatli (3 oy) | 16, 19, 20, 32, 33, 34, 41, 46 | Kengayish va daromad |
| ⚪ Uzoq muddatli (6 oy+) | 35, 36, 39, 44, 47, 49, 50 | Enterprise va miqyos |
