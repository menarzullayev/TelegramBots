# TezMath — Roadmap

## Umumiy holat: 45% tayyor

---

## ✅ Tayyor (ishlaydi)

| Komponent | Holat |
|---|---|
| Bot ishga tushish (polling + webhook) | ✅ |
| `/start`, `/help`, `/profile`, `/settings`, `/history`, `/admin` | ✅ |
| Matn masalasi → Claude API → javob | ✅ (dev mode) |
| Rasm masalasi → Claude API → javob | ✅ (dev mode) |
| Rate limiter (in-memory, dev) | ✅ |
| SQLite database (dev) | ✅ |
| Inline keyboard menyu | ✅ |
| UZ / RU i18n | ✅ |
| Yechimga baho berish (1–5 ⭐) | ✅ |
| GitHub Actions CI pipeline | ✅ |
| Docker Compose strukturasi | ✅ |
| nginx config | ✅ |
| Prometheus + alert qoidalar | ✅ |

---

## ❌ Implement qilinmagan

### 🔴 Kritik — Production ga chiqish uchun shart

| # | Vazifa | Tavsif |
|---|---|---|
| 1 | **Redis rate limiter** | `rate_limit.py` hozir in-memory — server restart bo'lsa hisoblar o'chadi |
| 2 | **RabbitMQ queue** | `queue_producer.py` to'g'ridan Claude chaqiryapti — ai-solver worker ulangan emas |
| 3 | **PostgreSQL ulash** | Production DB kerak, hozir SQLite ishlatyapti |
| 4 | **Webhook + HTTPS** | Domain + SSL sertifikat (nginx + certbot) kerak |
| 5 | **Bot error handler** | Hozir `No error handlers registered` xatosi logda ko'rinib turibdi |
| 6 | **Referral bonus** | `apply_referral()` yozilgan lekin bonus hisoblash yo'q |

### 🟡 To'lov tizimi — Daromad uchun shart

| # | Vazifa | Tavsif |
|---|---|---|
| 7 | **Payme sandbox test** | `merchant_id` va `secret_key` kiritib to'liq oqimni sinash |
| 8 | **Click sandbox test** | Click merchant credentials bilan sinash |
| 9 | **Telegram Stars test** | Real Stars to'lovi sinash (hozir kod to'g'ri, test qilinmagan) |
| 10 | **Premium aktivatsiya oqimi** | To'lov → webhook → premium yonish — bog'lanmagan |
| 11 | **Obuna tugash eslatmasi** | Subscription expire bo'lganda foydalanuvchiga avtomatik xabar |

### 🟡 Admin Panel — Boshqaruv uchun

| # | Vazifa | Tavsif |
|---|---|---|
| 12 | **Admin panel UI** | REST API tayyor, frontend (React/Vue dashboard) yo'q |
| 13 | **Broadcast ishlash** | RabbitMQ yo'qligi sababli notification worker ulangan emas |
| 14 | **Ban/unban test** | `/ban` buyrug'i yozilgan, real test qilinmagan |

### 🟢 Sifat va Kengayish

| # | Vazifa | Tavsif |
|---|---|---|
| 15 | **LaTeX renderer ulash** | `renderer` service tayyor lekin bot bilan ulanmagan (`render_url` har doim `None`) |
| 16 | **GPT-4o fallback** | `fallback.py` tayyor, OpenAI API key bo'lsa avtomatik ishlaydi |
| 17 | **Gemini fallback** | `fallback.py` tayyor, Gemini API key bo'lsa avtomatik ishlaydi |
| 18 | **Grafana dashboards** | Prometheus tayyor, Grafana panel konfiguratsiyasi yozilmagan |
| 19 | **Loki logging** | Structured JSON log bor, Loki agent ulangan emas |
| 20 | **Integration testlar** | Faqat unit testlar bor, end-to-end test yo'q |
| 21 | **Load test (Locust)** | `locustfile.py` yozilmagan |
| 22 | **Rate limit reset API** | Admin rate limitni qo'lda reset qila olmaydi |

---

## Bosqichli Roadmap

### Bosqich 1 — Production Minimal
> Maqsad: botni real serverda xavfsiz ishlatish

```
[ ] 1. Redis rate limiter ulash
[ ] 2. PostgreSQL ulash + Alembic migration ishga tushirish
[ ] 3. Webhook rejimi: HTTPS domain + SSL (certbot)
[ ] 4. Bot error handler yozish (foydalanuvchiga do'stona xato xabari)
[ ] 5. .env.production fayli tayyorlash
[ ] 6. docker compose up production da sinash
```

**Natija:** Bot 7/24 ishonchli ishlaydi, ma'lumotlar saqlanadi.

---

### Bosqich 2 — To'lov va Daromad
> Maqsad: real to'lovlar qabul qilish

```
[ ] 7.  Payme sandbox → real merchant hisobi ulash
[ ] 8.  Click sandbox → real merchant hisobi ulash
[ ] 9.  Telegram Stars real test o'tkazish
[ ] 10. To'lov webhook → premium aktivatsiya to'liq oqim
[ ] 11. Obuna tugash scheduleri (APScheduler yoki Celery beat)
[ ] 12. Referral bonus: har bir taklif uchun +1 kun premium
[ ] 13. RabbitMQ ulash: ai-solver worker + notification worker
```

**Natija:** Bot daromad keltira boshlaydi.

---

### Bosqich 3 — Admin va Monitoring
> Maqsad: loyihani nazorat qilish va tahlil qilish

```
[ ] 14. Admin panel React frontend (dashboard: foydalanuvchilar, to'lovlar, statistika)
[ ] 15. Broadcast to'liq test (RabbitMQ + notification worker)
[ ] 16. Grafana dashboard: DAU, RPM, xatolar, daromad grafiklar
[ ] 17. Loki + Promtail: markaziy log yig'ish
[ ] 18. Alertmanager: Telegram kanal orqali xabar (Telegram webhook)
```

**Natija:** Hamma ko'rsatkichlar bir joyda ko'rinadi.

---

### Bosqich 4 — Kengayish va Sifat
> Maqsad: kengaytirish va mustahkamlash

```
[ ] 19. LaTeX renderer ulash: Claude yechimini PNG sifatida yuborish
[ ] 20. GPT-4o fallback: Claude ishlamasa avtomatik GPT-4o ga o'tish
[ ] 21. Gemini fallback: GPT-4o ishlamasa Gemini ga o'tish
[ ] 22. Integration testlar (pytest + real SQLite/Postgres)
[ ] 23. Load test: Locust bilan 1000 concurrent user simulatsiyasi
[ ] 24. Rate limit reset: admin /resetlimit <user_id> buyrug'i
[ ] 25. Foydalanuvchi hisobini o'chirish (GDPR)
```

**Natija:** Tizim kengayib, sifati oshadi.

---

## Texnik qarz (Tech Debt)

| Fayl | Muammo |
|---|---|
| `queue_producer.py` | Dev va prod uchun alohida implementatsiya kerak (strategy pattern) |
| `rate_limit.py` | In-memory va Redis — bitta interfeys orqali almashtirilishi kerak |
| `database/connection.py` | SQLite va PostgreSQL — alohida adapter kerak |
| `handlers/callbacks/menu_callback.py` | Command handlerlarni callback dan chaqirish — `update.message` muammosi qayta ko'rib chiqilishi kerak |
| `middleware/auth.py` | Banned foydalanuvchiga xabar yuborilmaydi |

---

## Versiyalar

| Versiya | Maqsad | Holat |
|---|---|---|
| `v0.1.0` | Dev mode: bot ishlaydi, Claude javob beradi | ✅ Tayyor |
| `v0.2.0` | Production minimal: Redis + PostgreSQL + webhook | 🔲 Rejalashtirilgan |
| `v0.3.0` | To'lov tizimi to'liq | 🔲 Rejalashtirilgan |
| `v0.4.0` | Admin panel UI + monitoring | 🔲 Rejalashtirilgan |
| `v1.0.0` | Barcha funksiyalar, load test o'tgan | 🔲 Rejalashtirilgan |
