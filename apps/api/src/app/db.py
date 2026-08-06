import asyncpg
from app.core.config import settings

_pool: asyncpg.Pool | None = None

"""
asyncioで非同期に接続を管理するためのPoolを取得する
接続先はsettings.database_urlで設定されているDB

Returns:
  asyncpg.Pool: 非同期に接続を管理するためのPool

Raises:
  RuntimeError: 接続が失敗した場合
"""
async def get_pool() -> asyncpg.Pool:
  global _pool
  if _pool is None:
    _pool = await asyncpg.create_pool(
      settings.database_url,
      min_size=1,
      max_size=5,
      statement_cache_size=0
    )
  return _pool