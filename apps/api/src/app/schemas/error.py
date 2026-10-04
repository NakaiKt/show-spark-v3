from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


ERROR_500 = {500: {"model": ErrorResponse, "description": "サーバーエラー"}}
