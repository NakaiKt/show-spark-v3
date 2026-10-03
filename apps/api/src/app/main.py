from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.routers import health, me

app = FastAPI(title="show-spark API")
app.include_router(health.router)
app.include_router(me.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    想定外の例外を {"detail": ...} の形式で返す
    """
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


handler = Mangum(app)
