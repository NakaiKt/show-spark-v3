from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import current_claims
from app.schemas.error import ErrorResponse
from app.schemas.user import MeGetResponse, MeUpdateResponse
from app.services import user

router = APIRouter()

# 認証済みのクレーム。Depends を引数の既定値に書かず、型として宣言する
Claims = Annotated[dict, Depends(current_claims)]

ERROR_401 = {401: {"model": ErrorResponse, "description": "トークン または sub が無い"}}


@router.get(
    "/me",
    response_model=MeGetResponse,
    responses={
        **ERROR_401,
        404: {"model": ErrorResponse, "description": "ユーザーが見つからない"},
    },
)
async def get_me(claims: Claims):
    return await user.get_user(claims)


@router.put(
    "/me",
    response_model=MeUpdateResponse,
    responses={
        **ERROR_401,
        409: {
            "model": ErrorResponse,
            "description": "emailが別アカウントで使用されている",
        },
    },
)
async def update_me(claims: Claims):
    return await user.sync_from_claims(claims)
