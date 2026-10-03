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
        OSError: DB に到達できない（接続拒否、名前解決の失敗など）
        asyncpg.PostgresError: DB が接続を拒否した（認証失敗、DB が存在しないなど）
        TimeoutError: 接続がタイムアウトした
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
