import os
from pyrogram import Client
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "gender_analyzer_session")

def test_telegram():
    print("--- Telegram Ulanish Testi ---")
    
    # Client yaratish (sessiya fayli loyiha papkasida saqlanadi)
    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir="." # Sessiya fayli asosiy papkada bo'lishi uchun
    )

    try:
        app.start()
        me = app.get_me()
        print(f"Muvaffaqiyatli ulandi!")
        print(f"Ism: {me.first_name}")
        print(f"Username: @{me.username}")
        print(f"ID: {me.id}")
        print(f"\nSessiya fayli '{SESSION_NAME}.session' yaratildi/yangilandi.")
        app.stop()
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    test_telegram()
