import jwt
from fastapi import Header, HTTPException, Request

from app.core.config import settings

"""
localの場合

jwtのclaumsを取得する
"""
def _jwt_claims_from_lambda(request: Request) -> dict | None:
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

"""
API Gatewayを通す場合

Bearerトークンからdecodeして認証取得
"""
def _claims_from_local(authorization: str | None) -> dict:
  if not settings.is_local:
    raise RuntimeError("ローカル用の認証経路はAPP_ENV=localでしか使えません")
  
  if not authorization or not authorization.startswith("Bearer "):
    raise HTTPException(status_code=401, detail="Unauthorized")

  token = authorization.removeprefix("Bearer ")
  try:
    return jwt.decode(token, options={"verify_signature": False})
  except jwt.PyJWTError:
    raise HTTPException(status_code = 401, detail = "Unauthorized")

"""
request, headerから認証情報を取得する
"""
async def current_claims(
  request: Request,
  authorization: str | None = Header(default = None),
) -> dict:
  claims = _jwt_claims_from_lambda(request)

  if claims:
    return claims

  return _claims_from_local(authorization)
  