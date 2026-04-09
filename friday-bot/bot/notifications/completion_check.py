"""Отметка выполнения задачи — silent push после окончания задачи."""

import logging
from datetime import datetime, timedelta

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from db.models import Task, User

logger = logging.getLogger(__name__)


def compute_check_at(task: Task, next_task_start: datetime | None, default_duration: int) -> datetime:
    """Вычислить момент отправки проверки выполнения.

    1. scheduled_at + duration_min (или default_duration если не указана)
    2. Если следующая задача начинается раньше — за 2 мин до неё
    """
    duration = task.duration_min if task.duration_min else default_duration
    check_at = task.scheduled_at + timedelta(minutes=duration)

    if next_task_start and next_task_start < check_at:
        check_at = next_task_start - timedelta(minutes=2)

    return check_at


def make_completion_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Inline-клавиатура для отметки выполнения."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, полностью", callback_data=f"completion:done:{task_id}"),
            InlineKeyboardButton("🔸 Частично", callback_data=f"completion:partial:{task_id}"),
        ],
        [
            InlineKeyboardButton("❌ Не выполнил", callback_data=f"completion:skip:{task_id}"),
        ],
    ])


async def send_completion_check(bot: Bot, task: Task, user: User) -> None:
    """Отправить silent push с запросом отметки выполнения."""
    await bot.send_message(
        chat_id=user.telegram_id,
        text=f"✅ Задача завершена: <b>{task.title}</b>\nВыполнил?",
        parse_mode="HTML",
        reply_markup=make_completion_keyboard(task.id),
        disable_notification=True,  # отметка выполнения — без звука
    )
    logger.info(
        "Проверка выполнения отправлена: user=%d task_id=%d",
        user.telegram_id, task.id,
    )
