from app.core.config import Settings

LOCAL_SETTINGS = Settings(
    app_env="local", database_url="postgres://user:pass@host:5432/db"
)
PROD_SETTINGS = Settings(
    app_env="prod", database_url="postgres://user:pass@host:5432/db"
)
