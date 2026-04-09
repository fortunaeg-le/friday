"""Инициализация Telegram-бота (python-telegram-bot v20, webhook)."""

from telegram.ext import Application

from core.config import settings
from bot.handlers.start import start_handler
from bot.handlers.add_task import add_task_handler


def create_bot_app() -> Application:
    """Создать и настроить экземпляр бота."""
    builder = Application.builder().token(settings.bot_token)

    # Отключаем встроенный updater — webhook обрабатывается через FastAPI
    builder.updater(None)

    application = builder.build()

    # Регистрация хендлеров
    application.add_handler(start_handler)
    application.add_handler(add_task_handler)

    return application
