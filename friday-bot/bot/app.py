"""Инициализация Telegram-бота (python-telegram-bot v20, webhook)."""

from telegram.ext import Application

from core.config import settings
from bot.handlers.start import start_handler
from bot.handlers.add_task import add_task_handler
from bot.handlers.completion import (
    completion_partial_handler,
    completion_done_handler,
    completion_skip_handler,
)
from bot.handlers.project import project_handler, projects_list_handler


def create_bot_app() -> Application:
    """Создать и настроить экземпляр бота."""
    builder = Application.builder().token(settings.bot_token)

    # Отключаем встроенный updater — webhook обрабатывается через FastAPI
    builder.updater(None)

    application = builder.build()

    # Регистрация хендлеров
    application.add_handler(start_handler)
    application.add_handler(add_task_handler)
    application.add_handler(project_handler)
    application.add_handler(projects_list_handler)
    # ConversationHandler должен быть раньше простых callback-хендлеров
    application.add_handler(completion_partial_handler)
    application.add_handler(completion_done_handler)
    application.add_handler(completion_skip_handler)

    return application
