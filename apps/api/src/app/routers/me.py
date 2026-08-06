from fastapi import APIRouter, Depends

from app.auth import current_claims
from app.services import user

router = APIRouter()


@router.get("/me")
async def me(claims: dict = Depends(current_claims)):
    return await user.sync_from_claims(claims)