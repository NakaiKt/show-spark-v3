import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import (
    _unverified_claims_from_token,
    _verified_claims_from_authorizer,
    current_claims,
)

from tests.const import LOCAL_SETTINGS, PROD_SETTINGS


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    """
    HTTPBearer が Authorization: Bearer <token> を解析した結果

    ヘッダの解析は HTTPBearer が担うため、単体テストでは解析済みの値を直接渡す
    """
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


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


class TestUnverifiedClaimsFromToken:
    @pytest.fixture(autouse=True)
    def local_env(self, monkeypatch):
        # 未検証の経路は APP_ENV=local でしか動かないため、既定を local にする
        monkeypatch.setattr("app.auth.settings", LOCAL_SETTINGS)

    def test_署名を検証せずにデコードする(self, make_token):
        # ローカルには Auth0 の署名を検証する API Gateway が無い。
        # alg=none の手作りトークンが通るのは意図した挙動
        token = make_token(sub="google-oauth2|1", email="a@b.c", name="太郎")

        claims = _unverified_claims_from_token(token)

        assert claims == {"sub": "google-oauth2|1", "email": "a@b.c", "name": "太郎"}

    # ヘッダの形式（スキーム違い、Bearer の後が空など）は HTTPBearer が None にする。
    # その確認はルートを通す統合テストで行う
    @pytest.mark.parametrize(
        "token",
        [
            None,  # HTTPBearer がヘッダ無し・形式違いと判定した
            "",  # 空
            "not-a-jwt",  # JWT として壊れている
        ],
    )
    def test_不正なトークンは500ではなく401を返す(self, token):
        with pytest.raises(HTTPException) as excinfo:
            _unverified_claims_from_token(token)

        assert excinfo.value.status_code == 401

    def test_local以外では未検証の経路が使えない(self, monkeypatch, make_token):
        # 誰でも偽造できるトークンを受け入れる経路なので、
        # 環境変数の設定ミスで本番に載る事故を構造的に塞ぐ
        monkeypatch.setattr("app.auth.settings", PROD_SETTINGS)
        token = make_token(sub="google-oauth2|1", email="a@b.c")

        with pytest.raises(RuntimeError):
            _unverified_claims_from_token(token)


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

            claims = await current_claims(_request(event), credentials=_bearer(forged))

            assert claims["sub"] == "REAL"

        async def test_Authorizerを通っていなければ認証を通さない(self, make_token):
            """
            aws.event が無い＝API Gateway を経由していない。
            この経路でヘッダを信じると検証なしで通ってしまう。
            """
            valid_looking = make_token(sub="google-oauth2|1", email="a@b.c")

            with pytest.raises(RuntimeError):
                await current_claims(_request(None), credentials=_bearer(valid_looking))

        async def test_クレームが空なら認証を通さない(self, make_token):
            """
            Authorizer の設定ミスで claims が空になったとき、
            ヘッダにフォールバックしてはならない。
            """
            event = _authorizer_event(claims={})
            forged = make_token(sub="FORGED", email="attacker@example.com")

            with pytest.raises(RuntimeError):
                await current_claims(_request(event), credentials=_bearer(forged))

    class TestLocal:
        @pytest.fixture(autouse=True)
        def setup(self, monkeypatch):
            monkeypatch.setattr("app.auth.settings", LOCAL_SETTINGS)

        async def test_APIGatewayが無い環境ではヘッダから読む(self, make_token):
            token = make_token(sub="google-oauth2|1", email="a@b.c")

            claims = await current_claims(_request(None), credentials=_bearer(token))

            assert claims["sub"] == "google-oauth2|1"

        async def test_トークンが無ければ401(self):
            with pytest.raises(HTTPException) as excinfo:
                await current_claims(_request(None), credentials=None)

            assert excinfo.value.status_code == 401
