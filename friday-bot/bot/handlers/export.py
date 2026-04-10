"""Хендлер /export — формирование и отправка JSON-файла с данными пользователя.

Структура JSON:
  stats      — completion_rate, trend, streak за всё время
  patterns   — best_days, worst_time_slots, most_skipped за всё время
  reflections — записи из daily_logs
  tasks_history — последние задачи (до 500)
"""

import io
import json
import logging
from datetime import date, datetime

from sqlalchemy import select
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db.database import async_session
from db.crud import get_or_create_user
from db.models import DailyLog, Task
from core.stats import (
    calc_completion_rate,
    calc_streak,
    calc_best_days,
    calc_worst_time_slots,
    calc_most_skipped,
    calc_category_stats,
)

logger = logging.getLogger(__name__)

_EPOCH = date(2000, 1, 1)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/export — собрать данные и отправить JSON-файлом."""
    await update.message.reply_text("⏳ Собираем данные, это займёт секунду...")

    today = date.today()

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)

        # --- Stats (за всё время) ---
        rate = await calc_completion_rate(session, user.id, _EPOCH, today)
        streak = await calc_streak(session, user.id)

        # --- Patterns ---
        best_days = await calc_best_days(session, user.id, _EPOCH, today)
        worst_slots = await calc_worst_time_slots(session, user.id, _EPOCH, today)
        most_skipped = await calc_most_skipped(session, user.id, _EPOCH, today, top_n=10)
        category_stats = await calc_category_stats(session, user.id, _EPOCH, today)

        # --- Reflections ---
        logs_stmt = (
            select(DailyLog)
            .where(DailyLog.user_id == user.id)
            .order_by(DailyLog.log_date.desc())
            .limit(365)
        )
        logs_result = await session.execute(logs_stmt)
        logs = logs_result.scalars().all()

        # --- Tasks history ---
        tasks_stmt = (
            select(Task)
            .where(Task.user_id == user.id)
            .order_by(Task.scheduled_at.desc())
            .limit(500)
        )
        tasks_result = await session.execute(tasks_stmt)
        tasks = tasks_result.scalars().all()

    # --- Сборка JSON ---
    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "user_id": user.telegram_id,
        "stats": {
            "completion_rate": round(rate, 4),
            "streak_days": streak,
        },
        "patterns": {
            "best_days": best_days,
            "worst_time_slots": worst_slots,
            "most_skipped": most_skipped,
            "category_stats": category_stats,
        },
        "reflections": [
            {
                "date": str(log.log_date),
                "mood": log.mood,
                "is_quiet_day": log.is_quiet_day,
                "text": log.reflection_text,
            }
            for log in logs
        ],
        "tasks_history": [
            {
                "id": t.id,
                "title": t.title,
                "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
                "duration_min": t.duration_min,
                "category": t.category,
                "status": t.status,
                "completion_pct": t.completion_pct,
            }
            for t in tasks
        ],
    }

    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"friday_export_{today}.json"

    await update.message.reply_document(
        document=io.BytesIO(json_bytes),
        filename=filename,
        caption=(
            f"📦 Экспорт данных\n"
            f"Задач: {len(tasks)} · Рефлексий: {len(logs)}"
        ),
    )
    logger.info("Экспорт выполнен для user=%d", user.telegram_id)


export_handler = CommandHandler("export", export_command)
