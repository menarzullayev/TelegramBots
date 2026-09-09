import asyncio
import sys
from modules.scraper import scraper
from modules.analyzer import analyzer
from modules.reporter import reporter

async def main():
    print("=== Telegram Gender Analyzer Bot ===")
    
    chat_input = input("Analiz qilinadigan kanal yoki guruh username/linkini kiriting: ")
    if not chat_input:
        print("Xatolik: Link kiritilmadi.")
        return

    # Yagona sessiya ochish
    async with scraper.app:
        # 1. A'zolarni yig'ish
        print("\n[1/3] A'zolar ro'yxati yig'ilmoqda...")
        chat_id, chat_title = await scraper.collect_members(chat_input)
        
        if not chat_id:
            print("Xatolik: Kanal ma'lumotlarini olib bo'lmadi.")
            return

        # 2. AI Tahlil
        print(f"\n[2/3] Gemini AI yordamida jinsni aniqlash boshlandi... ({chat_title})")
        await analyzer.analyze_chat_members(chat_id)

        # 3. Hisobot tayyorlash
        print("\n[3/3] Hisobot va grafiklar tayyorlanmoqda...")
        text_report, img_path = reporter.generate_report(chat_id, chat_title)
        
        print("\n" + "="*30)
        print(text_report)
        print("="*30)
        print(f"\nDiagramma saqlandi: {img_path}")
        print("\nIsh yakunlandi!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")
    except Exception as e:
        print(f"\nKutilmagan xatolik: {e}")
