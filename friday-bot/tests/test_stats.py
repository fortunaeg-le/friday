"""Юнит-тесты для core/stats.py."""

import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta

from db.models import User, Task, QuietDay, StatsCache
from core.stats import (
    calc_completion_rate,
    calc_trend,
    calc_streak,
    calc_best_days,
    calc_worst_time_slots,
    calc_category_stats,
    calc_most_skipped,
    generate_stats_cache,
    week_bounds,
    month_bounds,
    period_bounds,
    prev_period_bounds,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_user(session) -> User:
    user = User(telegram_id=999_000)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _make_task(user_id, title="Task", status="done", scheduled_date=None,
               hour=10, duration=60, category="работа", completion_pct=None):
    d = scheduled_date or date.today()
    return Task(
        user_id=user_id,
        title=title,
        scheduled_at=datetime(d.year, d.month, d.day, hour, 0),
        duration_min=duration,
        category=category,
        status=status,
        completion_pct=completion_pct,
    )


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def test_week_bounds():
    # 2025-04-07 is Monday
    start, end = week_bounds(date(2025, 4, 7))
    assert start == date(2025, 4, 7)
    assert end == date(2025, 4, 13)


def test_month_bounds():
    start, end = month_bounds(date(2025, 2, 15))
    assert start == date(2025, 2, 1)
    assert end == date(2025, 2, 28)


def test_prev_period_bounds_week():
    cur_start = date(2025, 4, 7)
    prev_start, prev_end = prev_period_bounds("week", cur_start)
    assert prev_start == date(2025, 3, 31)
    assert prev_end == date(2025, 4, 6)


def test_prev_period_bounds_month_jan():
    cur_start = date(2025, 1, 1)
    prev_start, prev_end = prev_period_bounds("month", cur_start)
    assert prev_start == date(2024, 12, 1)
    assert prev_end == date(2024, 12, 31)


# ---------------------------------------------------------------------------
# calc_completion_rate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completion_rate_all_done(session):
    user = await _make_user(session)
    today = date.today()
    for _ in range(3):
        session.add(_make_task(user.id, status="done", scheduled_date=today))
    await session.commit()

    rate = await calc_completion_rate(session, user.id, today, today)
    assert rate == 1.0


@pytest.mark.asyncio
async def test_completion_rate_partial(session):
    user = await _make_user(session)
    today = date.today()
    session.add(_make_task(user.id, status="done", scheduled_date=today))
    session.add(_make_task(user.id, status="partial", completion_pct=50, scheduled_date=today))
    session.add(_make_task(user.id, status="skipped", scheduled_date=today))
    await session.commit()

    rate = await calc_completion_rate(session, user.id, today, today)
    # (1.0 + 0.5 + 0.0) / 3 = 0.5
    assert abs(rate - 0.5) < 1e-6


@pytest.mark.asyncio
async def test_completion_rate_no_tasks(session):
    user = await _make_user(session)
    today = date.today()
    rate = await calc_completion_rate(session, user.id, today, today)
    assert rate == 0.0


# ---------------------------------------------------------------------------
# calc_trend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calc_trend_positive(session):
    user = await _make_user(session)
    today = date.today()
    cur_start, cur_end = week_bounds(today)
    prev_start, prev_end = prev_period_bounds("week", cur_start)

    # Текущая неделя: все done (rate=1.0)
    for d in [cur_start, cur_start + timedelta(days=1)]:
        session.add(_make_task(user.id, status="done", scheduled_date=d))
    # Предыдущая: все skipped (rate=0.0)
    for d in [prev_start, prev_start + timedelta(days=1)]:
        session.add(_make_task(user.id, status="skipped", scheduled_date=d))
    await session.commit()

    trend = await calc_trend(session, user.id, "week", cur_start)
    assert trend == 100.0  # +100 процентных пунктов


@pytest.mark.asyncio
async def test_calc_trend_negative(session):
    user = await _make_user(session)
    today = date.today()
    cur_start, cur_end = week_bounds(today)
    prev_start, prev_end = prev_period_bounds("week", cur_start)

    # Текущая неделя: все skipped (rate=0.0)
    session.add(_make_task(user.id, status="skipped", scheduled_date=cur_start))
    # Предыдущая: все done (rate=1.0)
    session.add(_make_task(user.id, status="done", scheduled_date=prev_start))
    await session.commit()

    trend = await calc_trend(session, user.id, "week", cur_start)
    assert trend == -100.0


# ---------------------------------------------------------------------------
# calc_streak
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calc_streak_basic(session):
    user = await _make_user(session)
    today = date.today()
    # 3 дня подряд перед сегодня: все done
    for i in range(1, 4):
        d = today - timedelta(days=i)
        session.add(_make_task(user.id, status="done", scheduled_date=d))
    await session.commit()

    streak = await calc_streak(session, user.id)
    assert streak == 3


@pytest.mark.asyncio
async def test_calc_streak_broken(session):
    user = await _make_user(session)
    today = date.today()
    # Вчера — done, позавчера — skipped (прерывает)
    session.add(_make_task(user.id, status="done", scheduled_date=today - timedelta(days=1)))
    session.add(_make_task(user.id, status="skipped", scheduled_date=today - timedelta(days=2)))
    await session.commit()

    streak = await calc_streak(session, user.id)
    assert streak == 1


@pytest.mark.asyncio
async def test_calc_streak_quiet_day_skipped(session):
    """Тихий день не прерывает серию."""
    user = await _make_user(session)
    today = date.today()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    three_days_ago = today - timedelta(days=3)

    # 2 и 3 дня назад — done; позавчера (1 день) — тихий день (нет задач)
    qd = QuietDay(user_id=user.id, specific_date=yesterday, is_active=True)
    session.add(qd)
    session.add(_make_task(user.id, status="done", scheduled_date=two_days_ago))
    session.add(_make_task(user.id, status="done", scheduled_date=three_days_ago))
    await session.commit()

    streak = await calc_streak(session, user.id)
    assert streak == 2  # тихий день пропущен, серия 2


# ---------------------------------------------------------------------------
# calc_best_days
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calc_best_days(session):
    user = await _make_user(session)
    today = date.today()
    # Понедельник этой недели
    mon = today - timedelta(days=today.weekday())
    tue = mon + timedelta(days=1)

    # Пн: 2 done → rate=1.0
    session.add(_make_task(user.id, status="done", scheduled_date=mon))
    session.add(_make_task(user.id, status="done", scheduled_date=mon, hour=14))
    # Вт: 1 skipped → rate=0.0
    session.add(_make_task(user.id, status="skipped", scheduled_date=tue))
    await session.commit()

    start, end = week_bounds(today)
    result = await calc_best_days(session, user.id, start, end)

    assert result[0]["weekday"] == 0  # Пн первый
    assert result[0]["rate"] == 1.0
    assert result[-1]["rate"] == 0.0


# ---------------------------------------------------------------------------
# calc_worst_time_slots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calc_worst_time_slots(session):
    user = await _make_user(session)
    today = date.today()

    # 09:00 — 2 задачи, обе skipped → fail_rate=1.0
    session.add(_make_task(user.id, status="skipped", hour=9, scheduled_date=today))
    session.add(_make_task(user.id, status="skipped", hour=9, scheduled_date=today))
    # 14:00 — 1 done, 1 skipped → fail_rate=0.5
    session.add(_make_task(user.id, status="done", hour=14, scheduled_date=today))
    session.add(_make_task(user.id, status="skipped", hour=14, scheduled_date=today))
    # 10:00 — 1 done → fail_rate=0.0
    session.add(_make_task(user.id, status="done", hour=10, scheduled_date=today))
    await session.commit()

    result = await calc_worst_time_slots(session, user.id, today, today, top_n=3)
    assert result[0]["hour"] == 9
    assert result[0]["fail_rate"] == 1.0
    assert result[1]["hour"] == 14


# ---------------------------------------------------------------------------
# calc_category_stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calc_category_stats(session):
    user = await _make_user(session)
    today = date.today()

    # работа: 2 done, 1 skipped → rate ≈ 0.667
    session.add(_make_task(user.id, status="done", category="работа", scheduled_date=today))
    session.add(_make_task(user.id, status="done", category="работа", scheduled_date=today, hour=11))
    session.add(_make_task(user.id, status="skipped", category="работа", scheduled_date=today, hour=12))
    # здоровье: 1 done → rate=1.0
    session.add(_make_task(user.id, status="done", category="здоровье", scheduled_date=today, hour=8))
    await session.commit()

    result = await calc_category_stats(session, user.id, today, today)
    cats = {r["category"]: r for r in result}

    assert cats["здоровье"]["rate"] == 1.0
    assert abs(cats["работа"]["rate"] - round(2/3, 3)) < 0.001


# ---------------------------------------------------------------------------
# calc_most_skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calc_most_skipped(session):
    user = await _make_user(session)
    today = date.today()

    # "Зарядка" — skipped 3 раза
    for h in [7, 8, 9]:
        session.add(_make_task(user.id, title="Зарядка", status="skipped",
                               hour=h, scheduled_date=today))
    # "Читать" — skipped 1 раз
    session.add(_make_task(user.id, title="Читать", status="skipped",
                           hour=20, scheduled_date=today))
    # "Работа" — done
    session.add(_make_task(user.id, title="Работа", status="done",
                           hour=10, scheduled_date=today))
    await session.commit()

    result = await calc_most_skipped(session, user.id, today, today, top_n=2)
    assert result[0]["title"] == "Зарядка"
    assert result[0]["skip_count"] == 3
    assert result[1]["title"] == "Читать"


# ---------------------------------------------------------------------------
# generate_stats_cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_stats_cache_creates(session):
    user = await _make_user(session)
    today = date.today()

    session.add(_make_task(user.id, status="done", scheduled_date=today))
    session.add(_make_task(user.id, status="skipped", scheduled_date=today, hour=11))
    await session.commit()

    cache = await generate_stats_cache(session, user.id, "week")
    assert cache.id is not None
    assert cache.user_id == user.id
    assert cache.period_type == "week"
    assert cache.total_tasks == 2
    assert 0 < cache.completion_rate <= 1.0


@pytest.mark.asyncio
async def test_generate_stats_cache_updates(session):
    """Повторный вызов обновляет запись, не создаёт дубликат."""
    user = await _make_user(session)
    today = date.today()
    session.add(_make_task(user.id, status="done", scheduled_date=today))
    await session.commit()

    cache1 = await generate_stats_cache(session, user.id, "week")
    cache2 = await generate_stats_cache(session, user.id, "week")

    assert cache1.id == cache2.id  # тот же ряд
