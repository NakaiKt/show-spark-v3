import asyncpg
from fastapi import HTTPException

from app.db import get_pool
from app.repositories import app_user


async def sync_from_claims(claims: dict) -> dict:
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await app_user.upsert(
                conn,
                sub=sub,
                email=email.lower(),
                name=claims.get("name"),
                picture=claims.get("picture"),
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail="このメールアドレスは別のアカウントで使われています",
            )
    return dict(row)