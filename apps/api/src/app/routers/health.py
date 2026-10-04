import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import get_pool

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health():
    """
    APIとDBの疎通状態を返す

    APIは応答できるがDBに届かない状態を区別するため、
    DBに到達できない場合は200ではなく503を返す
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("select 1")
    except Exception:
        # 接続失敗はOSError / asyncpg.PostgresError / TimeoutErrorなど多岐にわたる。
        # 種類で絞ると取りこぼすほうが害が大きいため広く受ける。
        # 例外の内容は接続文字列を含みうるため、レスポンスには載せずログにだけ残す
        logger.exception("ヘルスチェックのDB疎通に失敗しました")
        return JSONResponse(status_code=503, content={"status": "degraded"})

    return {"status": "ok"}
