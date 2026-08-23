from datetime import datetime

import pytest

from app import db
from tests.integration.conftest import TEST_SUB_PREFIX

pytestmark = pytest.mark.integration

SUB = f"{TEST_SUB_PREFIX}alice"
OTHER_SUB = f"{TEST_SUB_PREFIX}bob"
EMAIL = "alice@example.com"


def _auth(make_token, **claims) -> dict:
    return {"Authorization": f"Bearer {make_token(**claims)}"}


async def _fetch_user(sub: str):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("select * from app_user where sub = $1", sub)


async def _count_users() -> int:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "select count(*) from app_user where sub like $1", f"{TEST_SUB_PREFIX}%"
        )


async def test_トークンが無ければ401(client):
    res = await client.get("/me")

    assert res.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        {"email": EMAIL},
        {"sub": SUB},
        {},
    ],
)
async def test_subかemailが欠けていれば401(client, make_token, claims):
    res = await client.get("/me", headers=_auth(make_token, **claims))

    assert res.status_code == 401


async def test_初回アクセスでユーザーが作られる(client, make_token):
    res = await client.get(
        "/me",
        headers=_auth(make_token, sub=SUB, email=EMAIL, name="Alice", picture="p.png"),
    )

    assert res.status_code == 200
    body = res.json()
    assert body["sub"] == SUB
    assert body["email"] == EMAIL
    assert body["name"] == "Alice"
    assert body["picture"] == "p.png"

    # レスポンスだけでは実際に永続化されたか分からないためDBも確認する
    row = await _fetch_user(SUB)
    assert row is not None
    assert row["email"] == EMAIL


async def test_メールアドレスは小文字で保存される(client, make_token):
    res = await client.get(
        "/me", headers=_auth(make_token, sub=SUB, email="Alice@Example.COM")
    )

    assert res.json()["email"] == EMAIL
    row = await _fetch_user(SUB)
    assert row["email"] == EMAIL


async def test_2回呼んでも行は増えない(client, make_token):
    headers = _auth(make_token, sub=SUB, email=EMAIL)

    await client.get("/me", headers=headers)
    await client.get("/me", headers=headers)

    assert await _count_users() == 1


async def test_2回目はlast_login_atだけが進む(client, make_token):
    headers = _auth(make_token, sub=SUB, email=EMAIL)

    first = (await client.get("/me", headers=headers)).json()
    second = (await client.get("/me", headers=headers)).json()

    assert second["id"] == first["id"]
    assert second["created_at"] == first["created_at"]
    assert datetime.fromisoformat(second["last_login_at"]) > datetime.fromisoformat(
        first["last_login_at"]
    )


async def test_プロフィールは初回のみ取得し以降は上書きしない(client, make_token):
    """
    name / picture はユーザーが編集できる項目のため、
    ログインのたびにGoogle側の値で塗り潰してはいけない
    """
    await client.get(
        "/me",
        headers=_auth(make_token, sub=SUB, email=EMAIL, name="Alice", picture="p.png"),
    )

    res = await client.get(
        "/me",
        headers=_auth(make_token, sub=SUB, email=EMAIL, name="Renamed", picture="q.png"),
    )

    assert res.json()["name"] == "Alice"
    assert res.json()["picture"] == "p.png"


async def test_同じメールで別アカウントを作ろうとすると409(client, make_token):
    await client.get("/me", headers=_auth(make_token, sub=SUB, email=EMAIL))

    res = await client.get("/me", headers=_auth(make_token, sub=OTHER_SUB, email=EMAIL))

    assert res.status_code == 409
    # 失敗したのに行が増えていれば、中途半端なユーザーが残ることになる
    assert await _count_users() == 1
