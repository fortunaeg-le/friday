"""REST API статистики: GET /api/stats?period=week|month|all"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from db.database import async_session
from db.crud import get_or_create_user
from core.stats import (
    calc_completion_rate,
    calc_trend,
    calc_streak,
    calc_best_days,
    calc_worst_time_slots,
    calc_category_stats,
    calc_most_skipped,
    period_bounds,
    _tasks_in_range,
    _effective_completion,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["stats"])


class StatsResponse(BaseModel):
    period: str
    start_date: str
    end_date: str
    total_tasks: int
    completed_tasks: float      # эффективное число с учётом partial
    completion_rate: float      # 0–1
    trend_delta: float          # процентные пункты vs предыдущий период
    streak: int
    best_days: list[dict]
    worst_time_slots: list[dict]
    category_stats: list[dict]
    most_skipped: list[dict]


@router.get("", response_model=StatsResponse)
async def get_stats(
    telegram_id: int = Query(...),
    period: str = Query("week", regex="^(week|month|all)$"),
):
    """Полная статистика пользователя за период (week | month | all)."""
    today = date.today()

    if period == "all":
        # С самого начала
        end = today
        start = date(2000, 1, 1)
        period_type_for_trend = "month"
    else:
        period_type_for_trend = period
        start, end = period_bounds(period, today)

    async with async_session() as session:
        user, _ = await get_or_create_user(session, telegram_id)

        rate = await calc_completion_rate(session, user.id, start, end)
        trend = await calc_trend(session, user.id, period_type_for_trend, start) if period != "all" else 0.0
        streak = await calc_streak(session, user.id)
        best_days = await calc_best_days(session, user.id, start, end)
        worst_slots = await calc_worst_time_slots(session, user.id, start, end)
        cat_stats = await calc_category_stats(session, user.id, start, end)
        most_skipped = await calc_most_skipped(session, user.id, start, end)
        tasks = await _tasks_in_range(session, user.id, start, end)

    total = len(tasks)
    done_eff = round(sum(_effective_completion(t) for t in tasks), 2)

    return StatsResponse(
        period=period,
        start_date=str(start),
        end_date=str(end),
        total_tasks=total,
        completed_tasks=done_eff,
        completion_rate=round(rate, 4),
        trend_delta=trend,
        streak=streak,
        best_days=best_days,
        worst_time_slots=worst_slots,
        category_stats=cat_stats,
        most_skipped=most_skipped,
    )
