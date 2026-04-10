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
    get_partial_tasks_for_user,
)

# In-memory множество task_id для которых уже отправлена проверка выполнения
_sent_completion_checks: set[int] = set()

# In-memory: (user_id, window_start_iso) для дедупликации рекомендаций окон
_sent_window_suggestions: set[tuple[int, str]] = set()
from bot.notifications.morning_summary import send_morning_summary
from bot.notifications.task_reminder import send_task_reminder
from bot.notifications.completion_check import compute_check_at, send_completion_check
from bot.notifications.window_suggestion import find_free_windows, send_window_suggestion, send_partial_task_suggestion
from bot.notifications.stats_report import send_stats_report
from bot.notifications.quiet_day_summary import send_quiet_day_summary_request
from bot.notifications.evening_reflection import send_evening_reflection_request

logger = logging.getLogger(__name__)


async def job_check_reminders(bot) -> None:
    """Каждую минуту: проверить и отправить все просроченные напоминания.

    В тихий день напоминания НЕ отправляются.
    """
    now = datetime.utcnow()
    today = now.date()
    async with async_session() as session:
        reminders = await get_unsent_reminders(session, before=now)
        if not reminders:
            return
        logger.info("Найдено %d напоминаний для отправки", len(reminders))
        for reminder in reminders:
            try:
                user = reminder.task.user
                # Задача уже выполнена — напоминание не нужно
                if reminder.task.status in ("done", "skipped"):
                    await mark_reminder_sent(session, reminder.id)
                    continue
                # Тихий день → не отправлять напоминания (только пометить как sent)
                if await is_quiet_day_for_user(session, user.id, today):
                    await mark_reminder_sent(session, reminder.id)
                    continue
                await send_task_reminder(bot, reminder)
                await mark_reminder_sent(session, reminder.id)
            except Exception as exc:
                logger.error(
                    "Ошибка отправки напоминания id=%d: %s",
                    reminder.id, exc,
                )


async def job_morning_summaries(bot) -> None:
    """Ежедневно в 08:00 UTC: отправить утренние сводки всем пользователям.

    В тихий день — отправляем БЕЗ ЗВУКА (silent=True).
    """
    logger.info("Запуск рассылки утренних сводок")
    today = date.today()
    async with async_session() as session:
        users = await get_all_users(session)
        sent = 0
        for user in users:
            try:
                silent = await is_quiet_day_for_user(session, user.id, today)
                ok = await send_morning_summary(bot, user, session, silent=silent)
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

            # Также включаем частично выполненные задачи дня
            partial_tasks = await get_partial_tasks_for_user(session, user.id)

            if not subtasks and not partial_tasks:
                continue

            # Предпочитаем подзадачу, укладывающуюся в окно
            subtask = None
            if subtasks:
                subtask = next(
                    (s for s in subtasks if s.duration_min and s.duration_min <= gap_min),
                    subtasks[0],
                )

            try:
                if subtask:
                    sent = await send_window_suggestion(bot, user, subtask, window_start, window_end)
                elif partial_tasks:
                    # Нет подзадач — предложить вернуться к незавершённой задаче
                    sent = await send_partial_task_suggestion(bot, user, partial_tasks[0], window_start, window_end)
                else:
                    sent = False
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


async def job_evening_reflections(bot) -> None:
    """Ежедневно в 21:00 UTC: запросить вечернюю рефлексию.

    НЕ отправляется в тихий день (для тихих — quiet_day_summary в 21:30).
    Проверяет настройку evening_reflection.enabled для каждого пользователя.
    """
    today = date.today()
    async with async_session() as session:
        users = await get_all_users(session)
    for user in users:
        async with async_session() as session:
            # Тихий день — пропускаем (в 21:30 придёт quiet_day_summary)
            if await is_quiet_day_for_user(session, user.id, today):
                continue
            # Проверяем настройку enabled
            from db.crud import get_notification_settings
            settings = await get_notification_settings(session, user.id)
            cfg = next((s for s in settings if s["type"] == "evening_reflection"), None)
            if cfg and not cfg["enabled"]:
                continue
        try:
            await send_evening_reflection_request(bot, user)
        except Exception as exc:
            logger.error("Ошибка evening_reflection user=%d: %s", user.telegram_id, exc)


async def job_quiet_day_summaries(bot) -> None:
    """Ежедневно в 21:30 UTC: запросить рефлексию у пользователей в тихом дне."""
    today = date.today()
    async with async_session() as session:
        users = await get_all_users(session)
    for user in users:
        async with async_session() as session:
            if not await is_quiet_day_for_user(session, user.id, today):
                continue
        try:
            await send_quiet_day_summary_request(bot, user)
        except Exception as exc:
            logger.error("Ошибка quiet_day_summary user=%d: %s", user.telegram_id, exc)


async def job_weekly_stats(bot) -> None:
    """Воскресенье 20:00 UTC: отправить еженедельный отчёт всем пользователям."""
    logger.info("Рассылка еженедельной статистики")
    async with async_session() as session:
        users = await get_all_users(session)
    for user in users:
        try:
            await send_stats_report(bot, user, "week")
        except Exception as exc:
            logger.error("Ошибка weekly stats user=%d: %s", user.telegram_id, exc)


async def job_monthly_stats(bot) -> None:
    """1-е число 20:00 UTC: отправить ежемесячный отчёт всем пользователям."""
    logger.info("Рассылка ежемесячной статистики")
    async with async_session() as session:
        users = await get_all_users(session)
    for user in users:
        try:
            await send_stats_report(bot, user, "month")
        except Exception as exc:
            logger.error("Ошибка monthly stats user=%d: %s", user.telegram_id, exc)


def setup_scheduler(bot_app: Application) -> AsyncIOScheduler:
    """Создать и настроить планировщик.

    Джобы:
    - каждую минуту: проверка и отправка напоминаний
    - ежедневно 08:00 UTC: утренняя сводка
    - ежедневно 00:05 UTC: генерация напоминаний на завтра
    """
    bot = bot_app.bot
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Напоминания — каждые 15 секунд для быстрого отклика
    scheduler.add_job(
        job_check_reminders,
        trigger="interval",
        seconds=15,
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

    # Вечерний дневник — 21:00 UTC (не в тихий день)
    scheduler.add_job(
        job_evening_reflections,
        trigger=CronTrigger(hour=21, minute=0, timezone="UTC"),
        args=[bot],
        id="evening_reflections",
        replace_existing=True,
    )

    # Вечерняя сводка тихого дня — 21:30 UTC
    scheduler.add_job(
        job_quiet_day_summaries,
        trigger=CronTrigger(hour=21, minute=30, timezone="UTC"),
        args=[bot],
        id="quiet_day_summaries",
        replace_existing=True,
    )

    # Еженедельный отчёт статистики — воскресенье 20:00 UTC
    scheduler.add_job(
        job_weekly_stats,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone="UTC"),
        args=[bot],
        id="weekly_stats",
        replace_existing=True,
    )

    # Ежемесячный отчёт статистики — 1-е число 20:00 UTC
    scheduler.add_job(
        job_monthly_stats,
        trigger=CronTrigger(day=1, hour=20, minute=0, timezone="UTC"),
        args=[bot],
        id="monthly_stats",
        replace_existing=True,
    )

    return scheduler
