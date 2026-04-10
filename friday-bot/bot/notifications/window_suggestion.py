"""Рекомендации задач в свободные временные окна."""

import logging
from datetime import datetime, timedelta

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from core.config import settings
from db.models import User, Task, ProjectSubtask

logger = logging.getLogger(__name__)

# Минимальное свободное окно для рекомендации (минуты)
MIN_WINDOW_MIN = 20


def find_free_windows(
    tasks: list[Task],
    default_duration: int,
    min_gap_min: int = MIN_WINDOW_MIN,
) -> list[tuple[datetime, datetime]]:
    """Найти свободные промежутки между задачами дня.

    Возвращает список (window_start, window_end) только для будущих окон.
    """
    now = datetime.utcnow()

    scheduled = []
    for t in tasks:
        if t.scheduled_at is None:
            continue
        dur = t.duration_min if t.duration_min else default_duration
        end = t.scheduled_at + timedelta(minutes=dur)
        scheduled.append((t.scheduled_at, end))

    if not scheduled:
        return []

    scheduled.sort(key=lambda x: x[0])

    windows = []
    for i in range(len(scheduled) - 1):
        gap_start = scheduled[i][1]       # конец текущей задачи
        gap_end = scheduled[i + 1][0]     # начало следующей
        gap_min = (gap_end - gap_start).total_seconds() / 60

        # Окно должно быть достаточно длинным и хотя бы частично в будущем
        if gap_min >= min_gap_min and gap_end > now:
            windows.append((gap_start, gap_end))

    return windows


def _suggestion_keyboard(subtask_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Начать", callback_data=f"suggestion:start:{subtask_id}")],
        [
            InlineKeyboardButton("⏭ Отложить", callback_data="suggestion:skip"),
            InlineKeyboardButton("🔄 Другую", callback_data=f"suggestion:another:{subtask_id}"),
        ],
    ])


async def send_window_suggestion(
    bot: Bot,
    user: User,
    subtask: ProjectSubtask,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    """Отправить пользователю предложение заняться подзадачей в свободное окно.

    Возвращает True если сообщение отправлено.
    """
    gap_min = int((window_end - window_start).total_seconds() / 60)
    start_str = window_start.strftime("%H:%M")
    end_str = window_end.strftime("%H:%M")

    dur_str = f"{subtask.duration_min} мин" if subtask.duration_min else f"~{gap_min} мин"

    text = (
        f"💡 <b>Свободное окно {start_str}–{end_str}</b> ({gap_min} мин)\n\n"
        f"Предлагаю заняться подзадачей:\n"
        f"📝 <b>{subtask.title}</b>\n"
        f"⏱ {dur_str}"
    )

    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML",
            reply_markup=_suggestion_keyboard(subtask.id),
        )
        return True
    except Exception as exc:
        logger.error(
            "Ошибка отправки window_suggestion user=%d: %s",
            user.telegram_id, exc,
        )
        return False
