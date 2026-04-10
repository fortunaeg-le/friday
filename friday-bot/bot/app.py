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
from bot.handlers.suggestion import (
    suggestion_start_handler,
    suggestion_skip_handler,
    suggestion_another_handler,
)
from bot.handlers.stats import stats_handler
from bot.handlers.quiet_days import (
    quiet_days_handler,
    qd_weekday_handler,
)
from bot.notifications.quiet_day_summary import (
    qd_summary_text_handler,
    qd_summary_skip_handler,
)
from bot.handlers.reflection import reflection_text_handler, reflection_skip_handler
from bot.handlers.export import export_handler
from bot.handlers.settings import (
    settings_handler,
    settings_open_handler,
    settings_toggle_handler,
    settings_sound_handler,
    settings_setmin_handler,
    settings_back_handler,
)


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
    application.add_handler(suggestion_start_handler)
    application.add_handler(suggestion_skip_handler)
    application.add_handler(suggestion_another_handler)
    application.add_handler(stats_handler)
    application.add_handler(quiet_days_handler)
    application.add_handler(qd_weekday_handler)
    application.add_handler(qd_summary_skip_handler)
    # qd_summary_text_handler — group=1: перехватывает только пользователей в очереди QD
    application.add_handler(qd_summary_text_handler, group=1)
    application.add_handler(reflection_skip_handler)
    # reflection_text_handler — group=2: независимо от qd_summary_text_handler
    application.add_handler(reflection_text_handler, group=2)
    application.add_handler(export_handler)
    application.add_handler(settings_handler)
    application.add_handler(settings_open_handler)
    application.add_handler(settings_toggle_handler)
    application.add_handler(settings_sound_handler)
    application.add_handler(settings_setmin_handler)
    application.add_handler(settings_back_handler)
    # ConversationHandler должен быть раньше простых callback-хендлеров
    application.add_handler(completion_partial_handler)
    application.add_handler(completion_done_handler)
    application.add_handler(completion_skip_handler)

    return application
