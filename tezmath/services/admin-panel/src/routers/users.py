from auth import verify_token
from db import get_pool
from fastapi import APIRouter, Depends, Query

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str = Query(""),
    is_premium: bool | None = Query(None),
):
    pool = await get_pool()
    offset = (page - 1) * per_page
    conditions = []
    params = []

    if search:
        params.append(f"%{search}%")
        conditions.append(f"(full_name ILIKE ${len(params)} OR username ILIKE ${len(params)})")

    if is_premium is not None:
        params.append(is_premium)
        conditions.append(f"is_premium = ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params += [per_page, offset]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, telegram_id, username, full_name, is_premium, is_banned, created_at FROM users {where} ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
            *params,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM users {where}", *params[:-2])

    return {"total": total, "page": page, "items": [dict(r) for r in rows]}


@router.patch("/{user_id}/ban")
async def toggle_ban(user_id: int, banned: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_banned = $1, updated_at = NOW() WHERE id = $2",
            banned,
            user_id,
        )
    return {"ok": True}
