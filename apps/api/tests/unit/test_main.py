import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import current_claims
from app.main import app


@pytest.fixture
async def client_without_raise():
    """
    想定外の例外をレスポンスとして受け取るクライアント

    Starlette は 500 を返した後に例外を再送出する（サーバーがログに残すため）。
    既定のままだとテスト内で例外が上がり、返ったレスポンスを確かめられない
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def broken_auth():
    """認証の依存関数を、想定外の例外を投げるものに差し替える"""

    def _boom():
        raise ValueError("secret detail: password=xxx")

    app.dependency_overrides[current_claims] = _boom
    yield
    app.dependency_overrides.pop(current_claims, None)


class TestUnhandledException:
    async def test_想定外の例外はJSONの500で返る(
        self, client_without_raise, broken_auth
    ):
        res = await client_without_raise.get("/me")

        assert res.status_code == 500
        assert res.headers["content-type"] == "application/json"
        assert res.json() == {"detail": "Internal Server Error"}

    async def test_例外の内容はレスポンスに含めない(
        self, client_without_raise, broken_auth
    ):
        # 例外メッセージは接続文字列などを含みうる
        res = await client_without_raise.get("/me")

        assert "secret" not in res.text


class TestOpenApi500:
    @pytest.mark.parametrize(
        ("path", "method"),
        [
            ("/health", "get"),
            ("/me", "get"),
            ("/me", "put"),
        ],
    )
    def test_全ルートに500が宣言されている(self, path, method):
        # 500 はどのルートでも起こりうるため、アプリ全体で宣言している。
        # FastAPI は未知の引数を黙って受け取るので、引数名の誤りはここでしか気づけない
        responses = app.openapi()["paths"][path][method]["responses"]

        assert "500" in responses
        assert responses["500"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
