# GenderAnalyzerBot

Telegram kanallari va guruhlari a'zolarini Gemini AI yordamida gender bo'yicha tahlil qiluvchi bot.

## Loyiha Strukturasi

- `main.py`: Botni ishga tushirish uchun asosiy fayl.
- `modules/`:
    - `scraper.py`: A'zolar ro'yxatini yig'ish (Pyrogram).
    - `analyzer.py`: Gemini/Claude API orqali ismlarni tahlil qilish.
    - `database.py`: SQLite bilan ishlash (a'zolar ma'lumotlarini saqlash).
    - `reporter.py`: Statistika va grafiklar (Matplotlib) tayyorlash.
- `database/`: SQLite ma'lumotlar bazasi fayli saqlanadigan joy.
- `outputs/`: Generatsiya qilingan grafiklar (diagrammalar) saqlanadigan joy.
- `.env`: API kalitlar (maxfiy).
- `requirements.txt`: Kutubxonalar ro'yxati.

## O'rnatish

> Python 3.13 kerak. `pyrogram` 2.0.106 (oxirgi reliz) Python 3.14 da import bo'lmaydi (`RuntimeError: There is no current event loop`).

1. Virtual environment yarating va faollashtiring:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```

3. `.env.example` faylini `.env` deb o'zgartiring va API kalitlarni yozing.



'''

API key details
API Key (never commit the real key: put it in .env as GEMINI_API_KEY)
<YOUR_GEMINI_API_KEY>
Name
GenderAnalyzerBot
Project name
projects/81383346231
Project number
81383346231

curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent" \
  -H 'Content-Type: application/json' \
  -H 'X-goog-api-key: <YOUR_GEMINI_API_KEY>' \
  -X POST \
  -d '{
    "contents": [
      {
        "parts": [
          {
            "text": "Explain how AI works in a few words"
          }
        ]
      }
    ]
  }'

  <YOUR_GEMINI_API_KEY>
'''