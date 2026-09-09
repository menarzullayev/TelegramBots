import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def list_models():
    print("--- Mavjud Gemini Modellari Ro'yxati ---")
    if not GEMINI_API_KEY:
        print("Xatolik: GEMINI_API_KEY topilmadi!")
        return

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        print(f"{'Model Nomi':<40} | {'Display Name'}")
        print("-" * 60)
        
        for model in client.models.list():
            # Atributlarni tekshirish uchun bitta modelni to'liq chiqaramiz
            # print(model) 
            print(f"{model.name:<40} | {model.display_name}")
                
    except Exception as e:
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    list_models()
