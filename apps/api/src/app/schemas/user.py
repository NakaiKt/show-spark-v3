from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MeGetResponse(BaseModel):
    id: UUID
    sub: str
    email: str
    name: str | None
    picture: str | None
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime


class MeUpdateRequest(MeGetResponse):
    pass
