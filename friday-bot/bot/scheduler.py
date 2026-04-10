"""APScheduler — все джобы планировщика задач."""

import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from core.config import settings
from db.database import async_session
from db.crud import (
    get_all_users,
    get_unsent_reminders,
    mark_reminder_sent,
    generate_reminders_for_date,
    get_tasks_by_date,
    get_tasks_for_completion_check,
    is_quiet_day_for_user,
    get_pending_subtasks_for_user,
)

# In-memory множество task_id для которых уже отправлена проверка выполнения
_sent_completion_checks: set[int] = set()

# In-memory: (user_id, window_start_iso) для дедупликации рекомендаций окон
_sent_window_suggestions: set[tuple[int, str]] = set()
from bot.notifications.morning_summary import send_morning_summary
from bot.notifications.task_reminder import send_task_reminder
from bot.notifications.completion_check import compute_check_at, send_completion_check
from bot.notifications.window_suggestion import find_free_windows, send_window_suggestion

logger = logging.getLogger(__name__)


async def job_check_reminders(bot) -> None:
    """Каждую минуту: проверить и отправить все просроченные напоминания."""
    now = datetime.utcnow()
    async with async_session() as session:
        reminders = await get_unsent_reminders(session, before=now)
        if not reminders:
            return
        logger.info("Найдено %d напоминаний для отправки", len(reminders))
        for reminder in reminders:
            try:
                await send_task_reminder(bot, reminder)
                await mark_reminder_sent(session, reminder.id)
            except Exception as exc:
                logger.error(
                    "Ошибка отправки напоминания id=%d: %s",
                    reminder.id, exc,
                )


async def job_morning_summaries(bot) -> None:
    """Ежедневно в 08:00 UTC: отправить утренние сводки всем пользователям."""
    logger.info("Запуск рассылки утренних сводок")
    async with async_session() as session:
        users = await get_all_users(session)
        sent = 0
        for user in users:
            try:
                ok = await send_morning_summary(bot, user, session)
                if ok:
                    sent += 1
            except Exception as exc:
                logger.error(
                    "Ошибка утренней сводки для user=%d: %s",
                    user.telegram_id, exc,
                )
    logger.info("Утренние сводки отправлены: %d/%d", sent, len(users))


async def job_check_completions(bot) -> None:
    """Каждую минуту: отправить проверки выполнения для завершившихся задач."""
    now = datetime.utcnow()
    today = now.date()
    async with async_session() as session:
        users = await get_all_users(session)
        for user in users:
            # Не отправлять в тихий день
            if await is_quiet_day_for_user(session, user.id, today):
                continue

            pending_tasks = await get_tasks_for_completion_check(session, user.id, today)
            if not pending_tasks:
                continue

            # Все задачи дня для определения "следующей задачи"
            all_today = await get_tasks_by_date(session, user.id, today)
            starts = sorted(
                [t.scheduled_at for t in all_today if t.scheduled_at],
                key=lambda dt: dt,
            )

            for task in pending_tasks:
                if task.id in _sent_completion_checks:
                    continue
                next_start = next(
                    (s for s in starts if s > task.scheduled_at), None
                )
                check_at = compute_check_at(task, next_start, settings.default_task_duration)
                if check_at <= now:
                    try:
                        await send_completion_check(bot, task, user)
                        _sent_completion_checks.add(task.id)
                    except Exception as exc:
                        logger.error(
                            "Ошибка отправки completion check task_id=%d: %s",
                            task.id, exc,
                        )


async def job_check_window_suggestions(bot) -> None:
    """Каждые 30 минут: найти свободные окна и предложить подзадачу."""
    now = datetime.utcnow()
    today = now.date()
    async with async_session() as session:
        users = await get_all_users(session)
        for user in users:
            # Не отправлять в тихий день
            if await is_quiet_day_for_user(session, user.id, today):
                continue

            tasks = await get_tasks_by_date(session, user.id, today)
            windows = find_free_windows(tasks, settings.default_task_duration)
            if not windows:
                continue

            # Берём первое актуальное окно
            window_start, window_end = windows[0]
            dedup_key = (user.id, window_start.strftime("%Y-%m-%dT%H:%M"))
            if dedup_key in _sent_window_suggestions:
                continue

            # Ищем подходящую pending подзадачу
            gap_min = int((window_end - window_start).total_seconds() / 60)
            subtasks = await get_pending_subtasks_for_user(session, user.id)
            if not subtasks:
                continue

            # Предпочитаем подзадачу, укладывающуюся в окно
            subtask = next(
                (s for s in subtasks if s.duration_min and s.duration_min <= gap_min),
                subtasks[0],
            )

            try:
                sent = await send_window_suggestion(bot, user, subtask, window_start, window_end)
                if sent:
                    _sent_window_suggestions.add(dedup_key)
            except Exception as exc:
                logger.error(
                    "Ошибка window_suggestion user=%d: %s",
                    user.telegram_id, exc,
                )


async def job_generate_reminders() -> None:
    """Ежедневно в 00:05 UTC: создать напоминания для задач на завтра."""
    tomorrow = date.today() + timedelta(days=1)
    logger.info("Генерация напоминаний на %s", tomorrow)
    async with async_session() as session:
        users = await get_all_users(session)
        for user in users:
            try:
                await generate_reminders_for_date(session, user.id, tomorrow)
            except Exception as exc:
                logger.error(
                    "Ошибка генерации напоминаний для user=%d: %s",
                    user.telegram_id, exc,
                )


def setup_scheduler(bot_app: Application) -> AsyncIOScheduler:
    """Создать и настроить планировщик.

    Джобы:
    - каждую минуту: проверка и отправка напоминаний
    - ежедневно 08:00 UTC: утренняя сводка
    - ежедневно 00:05 UTC: генерация напоминаний на завтра
    """
    bot = bot_app.bot
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Напоминания — каждую минуту
    scheduler.add_job(
        job_check_reminders,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="check_reminders",
        replace_existing=True,
    )

    # Отметки выполнения — каждую минуту
    scheduler.add_job(
        job_check_completions,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="check_completions",
        replace_existing=True,
    )

    # Утренняя сводка — 08:00 UTC
    scheduler.add_job(
        job_morning_summaries,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        args=[bot],
        id="morning_summary",
        replace_existing=True,
    )

    # Генерация напоминаний на завтра — 00:05 UTC
    scheduler.add_job(
        job_generate_reminders,
        trigger=CronTrigger(hour=0, minute=5, timezone="UTC"),
        id="generate_reminders",
        replace_existing=True,
    )

    # Рекомендации в свободные окна — каждые 30 минут
    scheduler.add_job(
        job_check_window_suggestions,
        trigger="interval",
        minutes=30,
        args=[bot],
        id="window_suggestions",
        replace_existing=True,
    )

    return scheduler
