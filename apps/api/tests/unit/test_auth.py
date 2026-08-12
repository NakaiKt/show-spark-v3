import pytest
from fastapi import HTTPException

from app.auth import (
    _unverified_claims_from_header,
    _verified_claims_from_authorizer,
    current_claims,
)
from app.core.config import Settings

LOCAL_SETTINGS = Settings(
    app_env="local", database_url="postgres://user:pass@host:5432/db"
)
PROD_SETTINGS = Settings(
    app_env="prod", database_url="postgres://user:pass@host:5432/db"
)


def _request(event: dict | None):
    """
    auth.pyはrequest.scopeしか参照しないため、最小のダミーで足りる

    eventがNoneのときはAPI Gatewayを経由していない状態を表す
    """

    class _DummyRequest:
        scope = {} if event is None else {"aws.event": event}

    return _DummyRequest()


def _authorizer_event(claims: dict | None) -> dict:
    """
    API Gateway HTTP API + JWT Authorizer が Lambda に渡すイベント構造
    """
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}


class TestVerifiedClaimsFromAuthorizer:
    def test_APIGatewayのイベント構造からクレームを取り出せる(self):
        # requestContext.authorizer.jwt.claims のパスは API Gateway が固定で使う形。
        # ここを間違えるとローカルでは動いて本番だけ落ちる
        event = {
            "version": "2.0",
            "routeKey": "$default",
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": "google-oauth2|1", "email": "a@b.c"},
                        "scopes": None,
                    }
                }
            },
        }

        claims = _verified_claims_from_authorizer(_request(event))

        assert claims == {"sub": "google-oauth2|1", "email": "a@b.c"}

    # pytest.mark.parametrizeを使うと、テスト関数の引数に渡す値を複数パターン指定できる
    @pytest.mark.parametrize(
        "event",
        [
            None,  # API Gateway を経由していない。aws.event が無い
            {"requestContext": {}},  # authorizer が無い
            {"requestContext": {"authorizer": {}}},  # jwt が無い
            _authorizer_event(claims={}),  # クレームが空
            _authorizer_event(claims=None),  # クレームが None
        ],
    )
    def test_クレームが取れない形ならNoneを返す(self, event):
        assert _verified_claims_from_authorizer(_request(event)) is None


class TestUnverifiedClaimsFromHeader:
    @pytest.fixture(autouse=True)
    def local_env(self, monkeypatch):
        # 未検証の経路は APP_ENV=local でしか動かないため、既定を local にする
        monkeypatch.setattr("app.auth.settings", LOCAL_SETTINGS)

    def test_署名を検証せずにデコードする(self, make_token):
        # ローカルには Auth0 の署名を検証する API Gateway が無い。
        # alg=none の手作りトークンが通るのは意図した挙動
        token = make_token(sub="google-oauth2|1", email="a@b.c", name="太郎")

        claims = _unverified_claims_from_header(f"Bearer {token}")

        assert claims == {"sub": "google-oauth2|1", "email": "a@b.c", "name": "太郎"}

    @pytest.mark.parametrize(
        "header",
        [
            None,  # ヘッダ無し
            "",  # 空
            "Basic abc",  # 別スキーム
            "Bearer",  # 空白なし
            "Bearer ",  # 中身なし
            "Bearer not-a-jwt",  # JWT として壊れている
        ],
    )
    def test_不正なヘッダは500ではなく401を返す(self, header):
        with pytest.raises(HTTPException) as excinfo:
            _unverified_claims_from_header(header)

        assert excinfo.value.status_code == 401

    def test_スキーム名が小文字のときは受け付けない(self, make_token):
        # RFC 6750 ではスキーム名は大文字小文字を区別しないが、
        # このAPIのクライアントは自前のフロントのみのため厳格に扱う
        token = make_token(sub="google-oauth2|1", email="a@b.c")

        with pytest.raises(HTTPException) as excinfo:
            _unverified_claims_from_header(f"bearer {token}")

        assert excinfo.value.status_code == 401

    def test_local以外では未検証の経路が使えない(self, monkeypatch, make_token):
        # 誰でも偽造できるトークンを受け入れる経路なので、
        # 環境変数の設定ミスで本番に載る事故を構造的に塞ぐ
        monkeypatch.setattr("app.auth.settings", PROD_SETTINGS)
        token = make_token(sub="google-oauth2|1", email="a@b.c")

        with pytest.raises(RuntimeError):
            _unverified_claims_from_header(f"Bearer {token}")


class TestCurrentClaims:
    class TestProd:
        @pytest.fixture(autouse=True)
        def setup(self, monkeypatch):
            monkeypatch.setattr("app.auth.settings", PROD_SETTINGS)

        async def test_Authorizerの結果がヘッダより優先される(self, make_token):
            """
            本番で Authorizer が検証済みクレームを入れているとき、
            リクエストヘッダの内容は一切参照してはならない。
            """
            event = _authorizer_event(
                claims={"sub": "REAL", "email": "real@example.com"}
            )
            forged = make_token(sub="FORGED", email="attacker@example.com")

            claims = await current_claims(
                _request(event), authorization=f"Bearer {forged}"
            )

            assert claims["sub"] == "REAL"

        async def test_Authorizerを通っていなければ認証を通さない(self, make_token):
            """
            aws.event が無い＝API Gateway を経由していない。
            この経路でヘッダを信じると検証なしで通ってしまう。
            """
            valid_looking = make_token(sub="google-oauth2|1", email="a@b.c")

            with pytest.raises(RuntimeError):
                await current_claims(
                    _request(None), authorization=f"Bearer {valid_looking}"
                )

        async def test_クレームが空なら認証を通さない(self, make_token):
            """
            Authorizer の設定ミスで claims が空になったとき、
            ヘッダにフォールバックしてはならない。
            """
            event = _authorizer_event(claims={})
            forged = make_token(sub="FORGED", email="attacker@example.com")

            with pytest.raises(RuntimeError):
                await current_claims(_request(event), authorization=f"Bearer {forged}")

    class TestLocal:
        @pytest.fixture(autouse=True)
        def setup(self, monkeypatch):
            monkeypatch.setattr("app.auth.settings", LOCAL_SETTINGS)

        async def test_APIGatewayが無い環境ではヘッダから読む(self, make_token):
            token = make_token(sub="google-oauth2|1", email="a@b.c")

            claims = await current_claims(
                _request(None), authorization=f"Bearer {token}"
            )

            assert claims["sub"] == "google-oauth2|1"

        async def test_トークンが無ければ401(self):
            with pytest.raises(HTTPException) as excinfo:
                await current_claims(_request(None), authorization=None)

            assert excinfo.value.status_code == 401
