import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "database/members_data.db")

def test_database():
    print("--- SQLite Database Testi ---")
    
    # Ma'lumotlar bazasi papkasini tekshirish
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Papka yaratildi: {db_dir}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Test jadvalini yaratish
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        ''')
        
        cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("Test User",))
        conn.commit()
        
        cursor.execute("SELECT name FROM test_table")
        result = cursor.fetchone()
        
        if result[0] == "Test User":
            print(f"Ma'lumotlar bazasi muvaffaqiyatli ishga tushdi: {DB_PATH}")
            
        conn.close()
        # Test jadvalini tozalash (ixtiyoriy)
        # os.remove(DB_PATH) 
        
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    test_database()
