import random
import string
import uuid

from database.connection import get_db


def _rand_code() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def _fetchone(db, sql, params=()):
    cursor = await db.execute(sql, params)
    return await cursor.fetchone()


async def get_or_create_user(*, telegram_id: int, username: str | None, full_name: str) -> dict:
    db = await get_db()
    row = await _fetchone(db, "SELECT * FROM users WHERE telegram_id=?", (telegram_id,))

    if row:
        await db.execute(
            """UPDATE users SET username=?, full_name=?, updated_at=datetime('now')
               WHERE telegram_id=?""",
            (username, full_name, telegram_id),
        )
        await db.commit()
        return dict(row)

    cursor = await db.execute(
        "INSERT INTO users (telegram_id, username, full_name, referral_code) VALUES (?,?,?,?)",
        (telegram_id, username, full_name, _rand_code()),
    )
    await db.commit()
    row = await _fetchone(db, "SELECT * FROM users WHERE id=?", (cursor.lastrowid,))
    return dict(row)


async def is_user_banned(telegram_id: int) -> bool:
    db = await get_db()
    row = await _fetchone(db, "SELECT is_banned FROM users WHERE telegram_id=?", (telegram_id,))
    return bool(row and row["is_banned"])


async def get_user_stats(user_id: int) -> dict:
    db = await get_db()
    row = await _fetchone(
        db,
        """SELECT COUNT(s.id) AS total_solutions,
                  COALESCE(AVG(s.rating), 0.0) AS avg_rating,
                  u.created_at AS joined_at
           FROM users u
           LEFT JOIN solutions s ON s.user_id = u.id
           WHERE u.id=?
           GROUP BY u.created_at""",
        (user_id,),
    )
    if not row:
        return {"total_solutions": 0, "avg_rating": 0.0, "joined_at": "—"}
    return {
        "total_solutions": row["total_solutions"],
        "avg_rating": round(float(row["avg_rating"]), 1),
        "joined_at": str(row["joined_at"])[:10],
    }


async def get_solution_history(user_id: int, limit: int = 5) -> list[dict]:
    from datetime import datetime

    db = await get_db()
    cursor = await db.execute(
        """SELECT id, input_text, created_at FROM solutions
           WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        except Exception:
            pass
        result.append(d)
    return result


async def save_solution(
    *,
    user_id: int,
    input_type: str,
    input_text: str,
    solution_text: str,
    model_used: str,
    tokens_used: int,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO solutions (user_id, input_type, input_text, solution_text, model_used, tokens_used)
           VALUES (?,?,?,?,?,?)""",
        (user_id, input_type, input_text, solution_text, model_used, tokens_used),
    )
    await db.commit()
    return cursor.lastrowid


async def save_solution_rating(solution_id: int, user_id: int, stars: int):
    db = await get_db()
    await db.execute(
        "UPDATE solutions SET rating=? WHERE id=? AND user_id=?",
        (stars, solution_id, user_id),
    )
    await db.commit()


async def update_user_language(user_id: int, lang: str):
    db = await get_db()
    await db.execute(
        "UPDATE users SET language=?, updated_at=datetime('now') WHERE id=?",
        (lang, user_id),
    )
    await db.commit()


async def apply_referral(user_id: int, ref_code: str):
    db = await get_db()
    row = await _fetchone(db, "SELECT id FROM users WHERE referral_code=?", (ref_code,))
    if row and row["id"] != user_id:
        await db.execute(
            "UPDATE users SET referred_by=? WHERE id=? AND referred_by IS NULL",
            (row["id"], user_id),
        )
        await db.commit()


async def activate_premium(user_id: int, months: int, method: str, amount: int):
    db = await get_db()
    await db.execute(
        """UPDATE users SET is_premium=1,
           subscription_end=datetime('now',? || ' months'),
           updated_at=datetime('now') WHERE id=?""",
        (f"+{months}", user_id),
    )
    await db.execute(
        """INSERT INTO transactions (id, user_id, amount, method, status)
           VALUES (?,?,?,?,'completed')""",
        (str(uuid.uuid4()), user_id, amount, method),
    )
    await db.commit()


async def ban_user(telegram_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE users SET is_banned=1, updated_at=datetime('now') WHERE telegram_id=?",
        (telegram_id,),
    )
    await db.commit()


async def save_chat_message(
    *,
    chat_id: int,
    user_id: int,
    username: str | None,
    full_name: str,
    text: str | None,
    has_image: bool,
    image_desc: str | None,
    file_id: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO chat_messages
               (chat_id, user_id, username, full_name, text, has_image, image_desc, file_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (chat_id, user_id, username, full_name, text, int(has_image), image_desc, file_id),
    )
    await db.commit()


async def get_recent_chat_messages(chat_id: int, limit: int = 10) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT full_name, username, text, has_image, image_desc, file_id
           FROM chat_messages
           WHERE chat_id=?
           ORDER BY created_at DESC
           LIMIT ?""",
        (chat_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in reversed(rows)]


async def get_admin_stats() -> dict:
    db = await get_db()
    u = await _fetchone(
        db,
        """SELECT COUNT(*) AS total_users, SUM(is_premium) AS premium_users,
                  SUM(CASE WHEN created_at >= date('now','-7 days') THEN 1 ELSE 0 END) AS new_users_7d
           FROM users""",
    )
    s = await _fetchone(
        db,
        """SELECT COUNT(*) AS total_solutions,
                  SUM(CASE WHEN created_at >= date('now') THEN 1 ELSE 0 END) AS today_solutions
           FROM solutions""",
    )
    r = await _fetchone(
        db,
        """SELECT COALESCE(SUM(amount),0) AS monthly_revenue FROM transactions
           WHERE status='completed' AND created_at >= date('now','start of month')""",
    )
    return {
        "total_users": u["total_users"] or 0,
        "premium_users": u["premium_users"] or 0,
        "new_users_7d": u["new_users_7d"] or 0,
        "total_solutions": s["total_solutions"] or 0,
        "today_solutions": s["today_solutions"] or 0,
        "monthly_revenue": r["monthly_revenue"] or 0,
    }
