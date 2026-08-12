import os

# app.core.config は import された瞬間に load_settings() を実行する。
# app パッケージを import する前に環境変数を入れておく必要がある。
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = (
    "postgres://showspark:showspark@127.0.0.1:5432/showspark?sslmode=disable"
)

import base64
import json

import pytest


def _b64url(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


@pytest.fixture
def make_token():
    """
    署名なしのJWTを組み立てるファクトリを返す

    ローカル経路は署名を検証しないため、Auth0に接続せず
    任意のクレームを持つトークンを作れる
    """

    def _make(**claims) -> str:
        header = _b64url({"alg": "none", "typ": "JWT"})
        payload = _b64url(claims)
        return f"{header}.{payload}."

    return _make
