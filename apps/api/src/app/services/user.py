import asyncpg
from fastapi import HTTPException

from app.db import get_pool
from app.repositories import app_user


async def get_user(claims: dict) -> dict | None:
    """
    subからユーザー情報を取得する
    """
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await app_user.get_by_sub(conn, sub)

    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


async def sync_from_claims(claims: dict) -> dict:
    """
    Claimsからユーザー情報を同期する
    subが存在しない場合は新規作成、存在する場合は更新する

    claimsのユーザー情報を登録、同期したいときに使用する
    """
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
