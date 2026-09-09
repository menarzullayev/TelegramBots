from auth import verify_token
from db import get_pool
from fastapi import APIRouter, Depends, Query

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("")
async def list_payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
):
    pool = await get_pool()
    offset = (page - 1) * per_page
    where = "WHERE t.status = $1" if status else ""
    params = ([status] if status else []) + [per_page, offset]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT t.id, t.user_id, u.username, u.full_name,
                       t.amount, t.method, t.status, t.created_at
                FROM transactions t
                JOIN users u ON u.id = t.user_id
                {where}
                ORDER BY t.created_at DESC
                LIMIT ${len(params) - 1} OFFSET ${len(params)}""",
            *params,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM transactions t {where}",
            *params[:-2],
        )

    return {"total": total, "page": page, "items": [dict(r) for r in rows]}
