import os
import json
import asyncio
from google import genai
from modules.database import db
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))

class Analyzer:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = "gemini-3.1-flash-lite-preview"

    async def analyze_chat_members(self, chat_id):
        """Hali tahlil qilinmagan a'zolarni paketlab AI ga yuborish"""
        members = db.get_unanalyzed_members(chat_id)
        if not members:
            print("Tahlil qilinmagan yangi a'zolar topilmadi.")
            return

        print(f"Jami {len(members)} ta a'zo tahlil qilinishi kerak.")
        
        # Batching
        for i in range(0, len(members), BATCH_SIZE):
            batch = members[i:i + BATCH_SIZE]
            await self._process_batch(chat_id, batch)
            print(f"Progress: {min(i + BATCH_SIZE, len(members))}/{len(members)}")
            # RPM limitidan oshib ketmaslik uchun 4 soniya kutamiz
            await asyncio.sleep(4)

    async def _process_batch(self, chat_id, batch, retries=5):
        """Bitta paketni tahlil qilish (retry logikasi bilan)"""
        prompt_data = []
        for m in batch:
            prompt_data.append({
                "uid": m[0],
                "first": m[1] or "",
                "last": m[2] or "",
                "user": m[3] or ""
            })

        prompt = f"""
        Analyze the following list of Telegram users and determine their gender based on their Name, Surname, and Username.
        Consider cultural contexts. Categories: 'Male', 'Female', or 'Unknown'.
        Input Data: {json.dumps(prompt_data)}
        Return ONLY a JSON object where the key is the 'uid' and the value is the gender.
        """

        for attempt in range(retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                
                results = json.loads(response.text)
                for user_id, gender in results.items():
                    db.update_gender(int(user_id), chat_id, gender)
                return # Muvaffaqiyatli yakunlandi

            except Exception as e:
                if "503" in str(e) and attempt < retries - 1:
                    wait_time = (attempt + 1) * 10 # 10s, 20s, 30s...
                    print(f"Gemini band (503). {wait_time} soniyadan keyin qayta urunib ko'riladi... ({attempt+1}/{retries})")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"AI tahlilida xatolik: {e}")
                    break

analyzer = Analyzer()
