import os
import pytest

from app.core.config import Settings, load_settings


class TestConfig:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """
        初期セットアップ
        """
        try:
            # 環境変数の指定
            os.environ["APP_ENV"] = "test"
            os.environ["DATABASE_URL"] = (
                "postgres://showspark:showspark@127.0.0.1:5432/showspark?sslmode=disable"
            )
            yield
        finally:
            os.environ.pop("APP_ENV", "test")
            os.environ.pop(
                "DATABASE_URL",
                "postgres://showspark:showspark@127.0.0.1:5432/showspark?sslmode=disable",
            )

    class TestSettings:
        class TestIsLocal:
            def test_returns_true_when_app_env_is_local(self):
                # localのときにis_localがTrueを返すこと
                os.environ["APP_ENV"] = "local"

                settings = load_settings()
                assert settings.is_local is True

            def test_returns_false_when_app_env_is_not_local(self):
                # local以外のときにis_localがFalseを返すこと
                os.environ["APP_ENV"] = "production"

                settings = load_settings()
                assert settings.is_local is False

    class TestLoadSettings:
        def test_load_settings_returns_settings_object(self):
            # load_settingsがSettingsオブジェクトを返すこと

            settings = load_settings()
            assert isinstance(settings, Settings)
            assert settings.app_env == "test"
            assert settings.database_url == os.environ["DATABASE_URL"]

        def test_load_settings_raises_runtime_error_when_env_vars_missing(self):
            # 環境変数が未設定のときにRuntimeErrorを発生させること
            os.environ.pop("APP_ENV", None)
            os.environ.pop("DATABASE_URL", None)

            with pytest.raises(RuntimeError) as excinfo:
                load_settings()
            assert "環境変数が未設定です" in str(excinfo.value)
