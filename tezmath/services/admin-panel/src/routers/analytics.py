from auth import verify_token
from db import get_pool
from fastapi import APIRouter, Depends

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/overview")
async def overview():
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetchrow(
            """SELECT
                COUNT(*)                                               AS total,
                COUNT(*) FILTER (WHERE is_premium)                    AS premium,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE)    AS today_new,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS week_new
               FROM users"""
        )
        solutions = await conn.fetchrow(
            """SELECT
                COUNT(*)                                              AS total,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE)   AS today,
                COALESCE(AVG(rating), 0)                             AS avg_rating
               FROM solutions"""
        )
        revenue = await conn.fetchrow(
            """SELECT
                COALESCE(SUM(amount) FILTER (WHERE created_at >= date_trunc('month', NOW())), 0) AS monthly,
                COALESCE(SUM(amount), 0) AS total
               FROM transactions WHERE status = 'completed'"""
        )

    return {
        "users": dict(users),
        "solutions": dict(solutions),
        "revenue": dict(revenue),
    }


@router.get("/daily")
async def daily_stats(days: int = 30):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT
                DATE(created_at) AS date,
                COUNT(*) AS solutions,
                COUNT(DISTINCT user_id) AS active_users
               FROM solutions
               WHERE created_at >= NOW() - ($1 || ' days')::interval
               GROUP BY DATE(created_at)
               ORDER BY date""",
            str(days),
        )
    return [dict(r) for r in rows]
