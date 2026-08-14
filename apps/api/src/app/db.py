import asyncpg
from app.core.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """
    asyncioで非同期に接続を管理するためのPoolを取得する
    接続先はsettings.database_urlで設定されているDB

    Returns:
      asyncpg.Pool: 非同期に接続を管理するためのPool

    Raises:
      RuntimeError: 接続が失敗した場合
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url, min_size=1, max_size=5, statement_cache_size=0
        )
    return _pool


async def close_pool() -> None:
    """
    asyncioで非同期に接続を管理するためのPoolを閉じる
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
