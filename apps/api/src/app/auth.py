from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)

CLAIM_NAMESPACE = "https://show-spark/"
CLAIM_EMAIL = f"{CLAIM_NAMESPACE}email"
CLAIM_NAME = f"{CLAIM_NAMESPACE}name"
CLAIM_PICTURE = f"{CLAIM_NAMESPACE}picture"


def _verified_claims_from_authorizer(request: Request) -> dict | None:
    """
    API Gateway の JWT Authorizer が検証済みのクレームを取り出す

    署名の検証は AWS 側で完了しているため、この値はそのまま信頼してよい。
    Authorizer を経由していない場合は None を返す
    """
    event = request.scope.get("aws.event")

    if not event:
        return None

    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims")
    )
    return claims or None


def _unverified_claims_from_token(token: str | None) -> dict:
    """
    Authorization ヘッダのトークンを署名検証せずにデコードする

    ローカルには検証を行う API Gateway が存在しないための代替経路。
    誰でも偽造できるトークンを受け入れるため、APP_ENV=local 以外では例外を投げる
    """
    if not settings.is_local:
        raise RuntimeError("未検証の認証経路はAPP_ENV=localでしか使えません")

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def current_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    """
    リクエストから認証情報を取り出す

    Authorizer の検証済みクレームを優先し、取れない場合のみヘッダを見る。
    順序を入れ替えると、本番で偽造トークンを受け入れる経路ができる
    """
    claims = _verified_claims_from_authorizer(request)

    if claims:
        return claims

    return _unverified_claims_from_token(
        credentials.credentials if credentials else None
    )
