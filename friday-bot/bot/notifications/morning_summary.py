"""Утренняя сводка — отправляется пользователю ежедневно в настроенное время."""

import logging
from datetime import date

from telegram import Bot

from db.crud import get_tasks_by_date, get_projects_near_deadline
from db.models import User

logger = logging.getLogger(__name__)


def _format_task_line(task) -> str:
    """Форматировать одну строку задачи для сводки."""
    if task.scheduled_at:
        time_str = task.scheduled_at.strftime("%H:%M")
    else:
        time_str = "——:——"
    dur = f" ({task.duration_min} мин)" if task.duration_min else ""
    return f"  {time_str} — {task.title}{dur}"


async def send_morning_summary(bot: Bot, user: User, session) -> bool:
    """Сформировать и отправить утреннюю сводку пользователю.

    Возвращает True если сообщение отправлено, False если нечего показывать.
    """
    today = date.today()
    tasks = await get_tasks_by_date(session, user.id, today)
    projects = await get_projects_near_deadline(session, user.id, days_ahead=1)

    if not tasks and not projects:
        return False

    lines = ["🌅 <b>Доброе утро!</b>\n"]

    if tasks:
        lines.append("📅 <b>Задачи на сегодня:</b>")
        for t in tasks:
            lines.append(_format_task_line(t))

    if projects:
        lines.append("\n📌 <b>Дедлайн сегодня/завтра:</b>")
        for p in projects:
            deadline_str = p.deadline.strftime("%d.%m") if p.deadline else ""
            lines.append(f"  • {p.title}" + (f" ({deadline_str})" if deadline_str else ""))

    text = "\n".join(lines)

    # Утренняя сводка по умолчанию со звуком (sound_enabled=True в notification_defaults)
    await bot.send_message(
        chat_id=user.telegram_id,
        text=text,
        parse_mode="HTML",
        disable_notification=False,
    )
    logger.info("Утренняя сводка отправлена пользователю %d", user.telegram_id)
    return True
