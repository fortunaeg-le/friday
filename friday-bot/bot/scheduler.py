"""APScheduler — все джобы планировщика задач."""

import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from db.database import async_session
from db.crud import (
    get_all_users,
    get_unsent_reminders,
    mark_reminder_sent,
    generate_reminders_for_date,
)
from bot.notifications.morning_summary import send_morning_summary
from bot.notifications.task_reminder import send_task_reminder

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

    return scheduler
