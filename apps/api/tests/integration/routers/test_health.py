import pytest

pytestmark = pytest.mark.integration


async def test_dbに疎通できていれば200を返す(client):
    res = await client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_dbに繋がらないときは503を返す(client, monkeypatch):
    async def _fail():
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr("app.routers.health.get_pool", _fail)

    res = await client.get("/health")

    assert res.status_code == 503
    assert res.json() == {"status": "degraded"}


async def test_db障害時のレスポンスに例外の詳細を載せない(client, monkeypatch):
    """接続文字列が漏れないことを確認する"""

    async def _fail():
        raise ConnectionRefusedError("postgres://showspark:showspark@127.0.0.1:5432")

    monkeypatch.setattr("app.routers.health.get_pool", _fail)

    res = await client.get("/health")

    assert "showspark" not in res.text
