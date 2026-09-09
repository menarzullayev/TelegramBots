import os
import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait
from modules.database import db
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "gender_analyzer_session")

class Scraper:
    def __init__(self):
        self.app = Client(
            SESSION_NAME,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=".",
            no_updates=True  # Fon xabarlarini o'chirib qo'yamiz
        )

    async def collect_members(self, chat_identifier):
        """Kanal yoki guruh a'zolarini yig'ish"""
        try:
            # chat_identifier'ni tozalash (agar t.me link bo'lsa)
            clean_id = chat_identifier.replace("https://t.me/", "").replace("t.me/", "")
            
            chat = await self.app.get_chat(clean_id)
            chat_id = chat.id
            print(f"Skenaralash boshlandi: {chat.title} ({chat_id})")
            
            count = 0
            async for member in self.app.get_chat_members(chat_id):
                user = member.user
                if not user or user.is_bot:
                    continue
                
                db.add_or_update_member(
                    user_id=user.id,
                    chat_id=chat_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    is_deleted=user.is_deleted
                )
                count += 1
                if count % 100 == 0:
                    print(f"{count} ta a'zo yozildi...")

            return chat_id, chat.title

        except FloodWait as e:
            print(f"FloodWait: {e.value} soniya kutilmoqda...")
            await asyncio.sleep(e.value)
            return await self.collect_members(chat_identifier)
        except Exception as e:
            print(f"Skraperda xatolik: {e}")
            return None, None

scraper = Scraper()
