import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "database/members_data.db")

class Database:
    def __init__(self):
        # Papka mavjudligini tekshirish
        db_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """A'zolar jadvalini yaratish"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER,
                chat_id INTEGER,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                gender TEXT DEFAULT 'Unknown',
                is_deleted INTEGER DEFAULT 0,
                analyzed_at TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        self.conn.commit()

    def add_or_update_member(self, user_id, chat_id, first_name, last_name, username, is_deleted=0):
        """A'zoni bazaga qo'shish yoki ma'lumotlarini yangilash"""
        self.cursor.execute('''
            INSERT INTO members (user_id, chat_id, first_name, last_name, username, is_deleted)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                username=excluded.username,
                is_deleted=excluded.is_deleted
        ''', (user_id, chat_id, first_name, last_name, username, 1 if is_deleted else 0))
        self.conn.commit()

    def update_gender(self, user_id, chat_id, gender):
        """AI tahlilidan keyin jinsini yangilash"""
        self.cursor.execute('''
            UPDATE members 
            SET gender = ?, analyzed_at = ?
            WHERE user_id = ? AND chat_id = ?
        ''', (gender, datetime.now(), user_id, chat_id))
        self.conn.commit()

    def get_unanalyzed_members(self, chat_id):
        """Hali tahlil qilinmagan a'zolarni olish"""
        self.cursor.execute('''
            SELECT user_id, first_name, last_name, username 
            FROM members 
            WHERE chat_id = ? AND gender = 'Unknown' AND is_deleted = 0
        ''', (chat_id,))
        return self.cursor.fetchall()

    def get_stats(self, chat_id):
        """Statistikani olish (Erkak, Ayol, Unknown, Deleted)"""
        # O'chirilganlarni alohida sanash
        self.cursor.execute('SELECT COUNT(*) FROM members WHERE chat_id = ? AND is_deleted = 1', (chat_id,))
        deleted_count = self.cursor.fetchone()[0]

        # Jinslar bo'yicha (faqat o'chirilmaganlarni sanaymiz)
        self.cursor.execute('''
            SELECT gender, COUNT(*) 
            FROM members 
            WHERE chat_id = ? AND is_deleted = 0
            GROUP BY gender
        ''', (chat_id,))
        stats = dict(self.cursor.fetchall())
        
        if deleted_count > 0:
            stats['Deleted'] = deleted_count
            
        return stats

    def get_all_chats(self):
        """Bazadagi barcha chatlar ro'yxatini olish"""
        self.cursor.execute('SELECT DISTINCT chat_id FROM members')
        chat_ids = [row[0] for row in self.cursor.fetchall()]
        
        # Chat nomlarini olishga harakat qilamiz (agar bor bo'lsa)
        chats = []
        for cid in chat_ids:
            # Oxirgi ma'lumotdan chat nomi sifatida foydalanamiz (ixtiyoriy)
            chats.append({"id": cid, "name": f"Chat {cid}"})
        return chats

    def get_members_paginated(self, chat_id, search="", gender="All", offset=0, limit=50):
        """A'zolarni filtr va pagination bilan olish"""
        query = "SELECT * FROM members WHERE chat_id = ?"
        params = [chat_id]
        
        if search:
            query += " AND (first_name LIKE ? OR last_name LIKE ? OR username LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])
            
        if gender != "All":
            if gender == "Deleted":
                query += " AND is_deleted = 1"
            else:
                query += " AND gender = ? AND is_deleted = 0"
                params.append(gender)
        else:
            # Agar Deleted ni alohida filtr qilmasak, hammasini chiqaramiz
            pass

        query += " ORDER BY analyzed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        self.cursor.execute(query, params)
        columns = [column[0] for column in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_total_count(self, chat_id, search="", gender="All"):
        """Filtrga mos jami a'zolar soni"""
        query = "SELECT COUNT(*) FROM members WHERE chat_id = ?"
        params = [chat_id]
        
        if search:
            query += " AND (first_name LIKE ? OR last_name LIKE ? OR username LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])
            
        if gender != "All":
            if gender == "Deleted":
                query += " AND is_deleted = 1"
            else:
                query += " AND gender = ? AND is_deleted = 0"
                params.append(gender)

        self.cursor.execute(query, params)
        return self.cursor.fetchone()[0]

    def close(self):
        self.conn.close()

# Singleton ob'ekt yaratish
db = Database()
