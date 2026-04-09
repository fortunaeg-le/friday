"""Напоминание о задаче — отправляется за N минут до начала."""

import logging

from telegram import Bot

from db.models import Reminder

logger = logging.getLogger(__name__)


async def send_task_reminder(bot: Bot, reminder: Reminder) -> None:
    """Отправить напоминание о задаче пользователю.

    Ожидает, что reminder.task и reminder.task.user подгружены (selectinload).
    """
    task = reminder.task
    user = task.user

    # Вычислить за сколько минут напоминание
    if task.scheduled_at and reminder.remind_at:
        delta_sec = (task.scheduled_at - reminder.remind_at).total_seconds()
        minutes_before = max(1, int(delta_sec / 60))
        time_str = task.scheduled_at.strftime("%H:%M")
        header = f"⏰ Через {minutes_before} мин: <b>{task.title}</b>"
        subline = f"🕐 Начало в {time_str}"
    else:
        header = f"⏰ Напоминание: <b>{task.title}</b>"
        subline = ""

    lines = [header]
    if subline:
        lines.append(subline)
    if task.duration_min:
        lines.append(f"⏱ Длительность: {task.duration_min} мин")
    if task.category:
        lines.append(f"📂 {task.category}")

    text = "\n".join(lines)

    await bot.send_message(
        chat_id=user.telegram_id,
        text=text,
        parse_mode="HTML",
        # sound_enabled хранится в reminder; False → disable_notification=True (silent push)
        disable_notification=not reminder.sound_enabled,
    )
    logger.info(
        "Напоминание отправлено: user=%d task_id=%d",
        user.telegram_id,
        task.id,
    )
