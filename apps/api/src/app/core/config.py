import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """
    アプリケーションの設定

    環境変数を読み込み、環境地を保持するクラスを提供する
    """

    app_env: str
    database_url: str

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


def load_settings() -> Settings:
    missing = [k for k in ("APP_ENV", "DATABASE_URL") if not os.environ.get(k)]

    if missing:
        raise RuntimeError(f"環境変数が未設定です：{', '.join(missing)}")

    return Settings(
        app_env=os.environ["APP_ENV"],
        database_url=os.environ["DATABASE_URL"],
    )


settings = load_settings()
