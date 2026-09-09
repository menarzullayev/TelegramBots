import os
from google import genai
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def test_gemini():
    print("--- Gemini API Testi (Yangi SDK) ---")
    
    if not GEMINI_API_KEY:
        print("Xatolik: GEMINI_API_KEY .env faylida topilmadi!")
        return

    try:
        # Yangi Client yaratish
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Kontent generatsiya qilish
        response = client.models.generate_content(
            model="gemini-flash-latest", 
            contents="Salom Gemini! O'zbek tilida qisqacha javob ber: Sen kimsan?"
        )
        
        print(f"Muvaffaqiyatli javob olindi:\n")
        print(response.text)
        print(f"\nAPI kaliti to'g'ri ishlamoqda.")
        
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    test_gemini()
