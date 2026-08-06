from fastapi import APIRouter

from app.db import get_pool

router = APIRouter()


@router.get("/health")
async def health():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("select 1")
    return {"status": "ok"}