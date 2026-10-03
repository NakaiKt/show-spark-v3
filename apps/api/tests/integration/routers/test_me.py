from datetime import datetime

import pytest

from app import db
from tests.integration.conftest import TEST_SUB_PREFIX

pytestmark = pytest.mark.integration

SUB = f"{TEST_SUB_PREFIX}alice"
OTHER_SUB = f"{TEST_SUB_PREFIX}bob"
EMAIL = "alice@example.com"
NAME = "Alice"
PICTURE = "alice.png"


def _auth(make_token, **claims) -> dict:
    # ヘッダーにAuthorizationを付与する
    return {"Authorization": f"Bearer {make_token(**claims)}"}


async def _fetch_user(sub: str):
    # DBから直接取得
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("select * from app_user where sub = $1", sub)


async def _post_user(
    sub: str, email: str, name: str | None = None, picture: str | None = None
):
    # DBに直接登録する
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            insert into app_user (sub, email, name, picture, last_login_at)
            values ($1, $2, $3, $4, now())
            returning *
            """,
            sub,
            email,
            name,
            picture,
        )


async def _count_users() -> int:
    # DBに存在するテスト用ユーザーの件数を返す
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "select count(*) from app_user where sub like $1", f"{TEST_SUB_PREFIX}%"
        )


@pytest.mark.parametrize("method", ["GET", "PUT"])
class TestMeAuth:
    """/me の各メソッドに共通する認証。いずれも current_claims に依存する"""

    async def test_トークンが無ければ401(self, client, method):
        res = await client.request(method, "/me")

        assert res.status_code == 401

    @pytest.mark.parametrize(
        "claims",
        [
            {"email": EMAIL},
        ],
    )
    async def test_subかemailが欠けていれば401(
        self, client, make_token, method, claims
    ):
        res = await client.request(method, "/me", headers=_auth(make_token, **claims))

        assert res.status_code == 401


class TestGetMe:
    # 全テストで最初にユーザーを作っておく
    @pytest.fixture(autouse=True)
    async def setup(self):
        await _post_user(SUB, EMAIL, NAME, PICTURE)

    async def test_ユーザーが存在すれば取得できる(self, client, make_token):
        res = await client.get("/me", headers=_auth(make_token, sub=SUB, email=EMAIL))
        assert res.status_code == 200
        body = res.json()
        assert body["sub"] == SUB
        assert body["email"] == EMAIL
        assert body["name"] == NAME
        assert body["picture"] == PICTURE

    async def test_ユーザーが存在しなければ404が返る(self, client, make_token):
        res = await client.get(
            "/me", headers=_auth(make_token, sub=OTHER_SUB, email=EMAIL)
        )
        assert res.status_code == 404


class TestPutMe:
    async def test_emailが欠けていれば401(self, client, make_token):
        res = await client.put("/me", headers=_auth(make_token, sub=SUB))

        assert res.status_code == 401

    async def test_初回でユーザーが作られる(self, client, make_token):
        res = await client.put(
            "/me",
            headers=_auth(make_token, sub=SUB, email=EMAIL, name=NAME, picture=PICTURE),
        )

        assert res.status_code == 200
        body = res.json()
        assert body["sub"] == SUB
        assert body["email"] == EMAIL
        assert body["name"] == NAME
        assert body["picture"] == PICTURE

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
        headers = _auth(make_token, sub=SUB, email=EMAIL, name=NAME, picture=PICTURE)
        first = (await client.put("/me", headers=headers)).json()

        update_email = "update." + EMAIL
        fake_name = "update " + NAME
        fake_picture = "update " + PICTURE
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
