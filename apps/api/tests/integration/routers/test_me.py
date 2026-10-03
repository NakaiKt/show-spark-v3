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


@pytest.mark.parametrize("method", ["PUT"])
class TestMeAuth:
    """/me の各メソッドに共通する認証。いずれも current_claims に依存する"""

    async def test_トークンが無ければ401(self, client, method):
        res = await client.request(method, "/me")

        assert res.status_code == 401

    @pytest.mark.parametrize(
        "claims",
        [
            {"email": EMAIL},
            {"sub": SUB},
            {},
        ],
    )
    async def test_subかemailが欠けていれば401(
        self, client, make_token, method, claims
    ):
        res = await client.request(method, "/me", headers=_auth(make_token, **claims))

        assert res.status_code == 401


class TestPutMe:
    async def test_初回でユーザーが作られる(self, client, make_token):
        res = await client.put(
            "/me",
            headers=_auth(
                make_token, sub=SUB, email=EMAIL, name="Alice", picture="p.png"
            ),
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

    async def test_2回呼んでも行は増えない(self, client, make_token):
        headers = _auth(make_token, sub=SUB, email=EMAIL)

        await client.put("/me", headers=headers)
        await client.put("/me", headers=headers)

        assert await _count_users() == 1

    async def test_2回め以降はemailとlast_login_atだけが更新される(
        self, client, make_token
    ):
        name = "Alice"
        picture = "p.png"
        headers = _auth(make_token, sub=SUB, email=EMAIL, name=name, picture=picture)
        first = (await client.put("/me", headers=headers)).json()

        update_email = "alice.updated@example.com"
        fake_name = "Renamed"
        fake_picture = "q.png"
        second = (
            await client.put(
                "/me",
                headers=_auth(
                    make_token,
                    sub=SUB,
                    email=update_email,
                    name=fake_name,
                    picture=fake_picture,
                ),
            )
        ).json()

        assert second["id"] == first["id"]
        assert second["sub"] == first["sub"]
        assert first["email"] == EMAIL
        assert second["email"] == update_email
        assert second["name"] == first["name"]
        assert second["picture"] == first["picture"]

    async def test_同じメールで別アカウントを作ろうとすると409(
        self, client, make_token
    ):
        await client.put("/me", headers=_auth(make_token, sub=SUB, email=EMAIL))

        res = await client.put(
            "/me", headers=_auth(make_token, sub=OTHER_SUB, email=EMAIL)
        )

        assert res.status_code == 409
        # 失敗したのに行が増えていれば、中途半端なユーザーが残ることになる
        assert await _count_users() == 1
