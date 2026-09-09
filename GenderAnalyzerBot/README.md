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
API Key
AIzaSyDwfp5FSPZLCjHQjLmoBu4Wl7EHpqDL4vY
Name
GenderAnalyzerBot
Project name
projects/81383346231
Project number
81383346231

curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent" \
  -H 'Content-Type: application/json' \
  -H 'X-goog-api-key: AIzaSyDwfp5FSPZLCjHQjLmoBu4Wl7EHpqDL4vY' \
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

  AIzaSyDwfp5FSPZLCjHQjLmoBu4Wl7EHpqDL4vY
'''