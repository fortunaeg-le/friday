"""Логика подсчёта статистики (п. 6.6 ТЗ)."""

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, QuietDay, StatsCache


# ---------------------------------------------------------------------------
# Вспомогательные функции периодов
# ---------------------------------------------------------------------------

def week_bounds(ref: date) -> tuple[date, date]:
    """Понедельник–Воскресенье недели, содержащей ref."""
    start = ref - timedelta(days=ref.weekday())
    return start, start + timedelta(days=6)


def month_bounds(ref: date) -> tuple[date, date]:
    """Первый–последний день месяца, содержащего ref."""
    start = ref.replace(day=1)
    last = calendar.monthrange(ref.year, ref.month)[1]
    return start, ref.replace(day=last)


def period_bounds(period_type: str, ref: date = None) -> tuple[date, date]:
    """Возвращает (start, end) для текущего периода."""
    if ref is None:
        ref = date.today()
    if period_type == "week":
        return week_bounds(ref)
    return month_bounds(ref)


def prev_period_bounds(period_type: str, current_start: date) -> tuple[date, date]:
    """Возвращает (start, end) предыдущего периода."""
    if period_type == "week":
        prev_start = current_start - timedelta(weeks=1)
        return prev_start, prev_start + timedelta(days=6)
    # month: откатываемся на 1 месяц назад
    if current_start.month == 1:
        prev_start = current_start.replace(year=current_start.year - 1, month=12)
    else:
        prev_start = current_start.replace(month=current_start.month - 1)
    return month_bounds(prev_start)


async def _tasks_in_range(
    session: AsyncSession, user_id: int, start: date, end: date
) -> list[Task]:
    """Получить задачи пользователя за диапазон дат (по scheduled_at)."""
    dt_start = datetime.combine(start, datetime.min.time())
    dt_end = datetime.combine(end, datetime.max.time())
    stmt = (
        select(Task)
        .where(
            and_(
                Task.user_id == user_id,
                Task.scheduled_at >= dt_start,
                Task.scheduled_at <= dt_end,
            )
        )
        .order_by(Task.scheduled_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _effective_completion(task: Task) -> float:
    """Вклад задачи в completion_rate: done=1.0, partial=pct/100, иначе 0."""
    if task.status == "done":
        return 1.0
    if task.status == "partial":
        return (task.completion_pct or 0) / 100.0
    return 0.0


# ---------------------------------------------------------------------------
# 1. calc_completion_rate
# ---------------------------------------------------------------------------

async def calc_completion_rate(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
) -> float:
    """Процент выполненных задач (0–1), partial считается пропорционально."""
    tasks = await _tasks_in_range(session, user_id, start_date, end_date)
    if not tasks:
        return 0.0
    return sum(_effective_completion(t) for t in tasks) / len(tasks)


# ---------------------------------------------------------------------------
# 2. calc_trend
# ---------------------------------------------------------------------------

async def calc_trend(
    session: AsyncSession,
    user_id: int,
    period_type: str,
    period_start: date,
) -> float:
    """Дельта completion_rate к предыдущему периоду (в процентных пунктах)."""
    cur_start, cur_end = period_bounds(period_type, period_start)
    prev_start, prev_end = prev_period_bounds(period_type, cur_start)

    cur_rate = await calc_completion_rate(session, user_id, cur_start, cur_end)
    prev_rate = await calc_completion_rate(session, user_id, prev_start, prev_end)
    return round((cur_rate - prev_rate) * 100, 1)


# ---------------------------------------------------------------------------
# 3. calc_streak
# ---------------------------------------------------------------------------

async def _is_quiet(session: AsyncSession, user_id: int, check_date: date) -> bool:
    stmt = select(QuietDay).where(
        and_(QuietDay.user_id == user_id, QuietDay.is_active.is_(True))
    )
    result = await session.execute(stmt)
    for qd in result.scalars().all():
        if qd.specific_date and qd.specific_date == check_date:
            return True
        if qd.day_of_week is not None and qd.day_of_week == check_date.weekday():
            return True
    return False


async def calc_streak(session: AsyncSession, user_id: int) -> int:
    """Количество последовательных «рабочих» дней с completion_rate ≥ 50%.

    Тихие дни пропускаются (не прерывают серию).
    """
    streak = 0
    current = date.today() - timedelta(days=1)  # начинаем со вчера

    for _ in range(365):  # не дальше года
        if await _is_quiet(session, user_id, current):
            current -= timedelta(days=1)
            continue

        rate = await calc_completion_rate(session, user_id, current, current)
        tasks = await _tasks_in_range(session, user_id, current, current)

        # Если задач нет — не считаем в серию, но и не прерываем
        if not tasks:
            current -= timedelta(days=1)
            continue

        if rate >= 0.5:
            streak += 1
        else:
            break

        current -= timedelta(days=1)

    return streak


# ---------------------------------------------------------------------------
# 4. calc_best_days
# ---------------------------------------------------------------------------

async def calc_best_days(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Лучшие дни недели по среднему completion_rate.

    Возвращает список {"weekday": 0-6, "label": "Пн", "rate": 0.85}, отсортированный убыванием.
    """
    LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    tasks = await _tasks_in_range(session, user_id, start_date, end_date)

    by_day: dict[int, list[float]] = defaultdict(list)
    for t in tasks:
        if t.scheduled_at:
            wd = t.scheduled_at.weekday()
            by_day[wd].append(_effective_completion(t))

    result = []
    for wd, values in by_day.items():
        avg = sum(values) / len(values) if values else 0.0
        result.append({"weekday": wd, "label": LABELS[wd], "rate": round(avg, 3)})

    result.sort(key=lambda x: x["rate"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# 5. calc_worst_time_slots
# ---------------------------------------------------------------------------

async def calc_worst_time_slots(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
    top_n: int = 3,
) -> list[dict]:
    """Топ-N часовых слотов с наибольшим количеством невыполненных задач.

    Возвращает список {"hour": 14, "label": "14:00–15:00", "fail_rate": 0.7}.
    """
    tasks = await _tasks_in_range(session, user_id, start_date, end_date)

    total_by_hour: dict[int, int] = defaultdict(int)
    fail_by_hour: dict[int, int] = defaultdict(int)

    for t in tasks:
        if t.scheduled_at is None:
            continue
        hour = t.scheduled_at.hour
        total_by_hour[hour] += 1
        if t.status in ("skipped", "pending"):
            fail_by_hour[hour] += 1

    slots = []
    for hour, total in total_by_hour.items():
        fail_rate = fail_by_hour[hour] / total if total else 0.0
        slots.append({
            "hour": hour,
            "label": f"{hour:02d}:00–{(hour+1):02d}:00",
            "fail_rate": round(fail_rate, 3),
        })

    slots.sort(key=lambda x: x["fail_rate"], reverse=True)
    return slots[:top_n]


# ---------------------------------------------------------------------------
# 6. calc_category_stats
# ---------------------------------------------------------------------------

async def calc_category_stats(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Процент выполнения по категориям.

    Возвращает список {"category": "работа", "rate": 0.75, "total": 10, "done": 7.5}.
    """
    tasks = await _tasks_in_range(session, user_id, start_date, end_date)

    totals: dict[str, int] = defaultdict(int)
    done_sum: dict[str, float] = defaultdict(float)

    for t in tasks:
        cat = t.category or "другое"
        totals[cat] += 1
        done_sum[cat] += _effective_completion(t)

    result = []
    for cat, total in totals.items():
        done = done_sum[cat]
        result.append({
            "category": cat,
            "rate": round(done / total, 3) if total else 0.0,
            "total": total,
            "done": round(done, 2),
        })

    result.sort(key=lambda x: x["rate"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# 7. calc_most_skipped
# ---------------------------------------------------------------------------

async def calc_most_skipped(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
    top_n: int = 2,
) -> list[dict]:
    """Топ-N задач, которые чаще всего не выполняются (skipped / pending).

    Возвращает список {"title": "...", "skip_count": N, "total": M}.
    """
    tasks = await _tasks_in_range(session, user_id, start_date, end_date)

    skip_count: dict[str, int] = defaultdict(int)
    total_count: dict[str, int] = defaultdict(int)

    for t in tasks:
        total_count[t.title] += 1
        if t.status in ("skipped", "pending"):
            skip_count[t.title] += 1

    result = [
        {"title": title, "skip_count": skip_count[title], "total": total_count[title]}
        for title in total_count
        if skip_count[title] > 0
    ]
    result.sort(key=lambda x: x["skip_count"], reverse=True)
    return result[:top_n]


# ---------------------------------------------------------------------------
# 8. generate_stats_cache
# ---------------------------------------------------------------------------

async def generate_stats_cache(
    session: AsyncSession,
    user_id: int,
    period_type: str,
) -> StatsCache:
    """Рассчитать статистику за текущий период и записать в stats_cache.

    period_type: "week" | "month"
    """
    today = date.today()
    start, end = period_bounds(period_type, today)

    rate = await calc_completion_rate(session, user_id, start, end)
    trend = await calc_trend(session, user_id, period_type, start)

    tasks = await _tasks_in_range(session, user_id, start, end)
    total = len(tasks)
    completed = round(sum(_effective_completion(t) for t in tasks), 2)

    # Попытка найти существующую запись кэша
    stmt = select(StatsCache).where(
        and_(
            StatsCache.user_id == user_id,
            StatsCache.period_type == period_type,
            StatsCache.period_start == start,
        )
    )
    result = await session.execute(stmt)
    cache = result.scalar_one_or_none()

    if cache is None:
        cache = StatsCache(
            user_id=user_id,
            period_type=period_type,
            period_start=start,
        )
        session.add(cache)

    cache.completion_rate = round(rate, 4)
    cache.total_tasks = total
    cache.completed_tasks = int(completed)
    cache.trend_delta = trend
    cache.generated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(cache)
    return cache
