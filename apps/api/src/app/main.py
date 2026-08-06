from fastapi import FastAPI
from mangum import Mangum

from app.routers import health, me

app = FastAPI(title="show-spark API")
app.include_router(health.router)
app.include_router(me.router)

handler = Mangum(app)