"""Конфигурация приложения — загрузка переменных из .env через pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки приложения. Значения берутся из переменных окружения / .env файла."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Telegram
    bot_token: str
    webhook_url: str
    webhook_secret: str = ""

    # База данных
    database_url: str

    # Приложение
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # Длительность задачи по умолчанию (минуты)
    default_task_duration: int = 30

    # AI (заглушка для Фазы 2)
    openai_api_key: str = ""
    claude_api_key: str = ""

    # Mini App
    mini_app_url: str = ""


settings = Settings()
