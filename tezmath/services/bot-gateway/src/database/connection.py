import os

import aiosqlite

DB_PATH = os.getenv("SQLITE_PATH", "tezmath.db")

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _init_schema(_db)
    return _db


async def _init_schema(db: aiosqlite.Connection):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER UNIQUE NOT NULL,
            username        TEXT,
            full_name       TEXT NOT NULL,
            language        TEXT NOT NULL DEFAULT 'uz',
            is_premium      INTEGER NOT NULL DEFAULT 0,
            is_banned       INTEGER NOT NULL DEFAULT 0,
            subscription_end TEXT,
            referral_code   TEXT UNIQUE,
            referred_by     INTEGER REFERENCES users(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS solutions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            input_type    TEXT NOT NULL,
            input_text    TEXT NOT NULL DEFAULT '',
            solution_text TEXT NOT NULL,
            model_used    TEXT NOT NULL DEFAULT '',
            tokens_used   INTEGER NOT NULL DEFAULT 0,
            rating        INTEGER,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      INTEGER NOT NULL,
            method      TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            period      TEXT NOT NULL DEFAULT 'monthly',
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            username    TEXT,
            full_name   TEXT NOT NULL DEFAULT '',
            text        TEXT,
            has_image   INTEGER NOT NULL DEFAULT 0,
            image_desc  TEXT,
            file_id     TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_lookup
            ON chat_messages(chat_id, created_at DESC);
    """)
    await db.commit()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
