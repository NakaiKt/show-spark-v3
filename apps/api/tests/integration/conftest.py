import pytest
from httpx import ASGITransport, AsyncClient

from app import db
from app.main import app
from tests.const import LOCAL_SETTINGS

# テストが作った行だけを消すための目印。
# 実際のGoogleアカウントのsubはこの形にならないため、開発用のデータと衝突しない
TEST_SUB_PREFIX = "google-oauth2|test-"


@pytest.fixture(autouse=True)
def local_auth(monkeypatch):
    """統合テストは API Gateway を経由しないため、ローカルと同じ経路を通す"""
    monkeypatch.setattr("app.auth.settings", LOCAL_SETTINGS)


@pytest.fixture(scope="session", autouse=True)
async def require_db():
    """
    DBに繋がらないときに原因の分かるメッセージで止める

    これが無いと全テストにConnectionRefusedErrorが出るだけで、
    DBの起動忘れなのか実装の不具合なのか判別できない
    """
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("select 1")
    except Exception as e:  # noqa: BLE001
        pytest.exit(f"DBに接続できません。npm run local:db を実行してください: {e}")


async def _delete_test_users() -> None:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "delete from app_user where sub like $1", f"{TEST_SUB_PREFIX}%"
        )


@pytest.fixture(autouse=True)
async def clean_app_user():
    """
    テストが作った行を前後で消す

    前にも消すのは、前回の実行が途中で落ちて行が残っている場合に備えるため
    """
    await _delete_test_users()
    yield
    await _delete_test_users()


@pytest.fixture
async def client():
    """
    アプリを直接叩くHTTPクライアント

    ASGITransportはネットワークを介さずアプリを呼ぶため、
    サーバーを別途起動する必要がない
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
