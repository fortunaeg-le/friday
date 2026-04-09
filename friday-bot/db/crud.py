"""CRUD-операции с базой данных."""

from datetime import datetime, date, timedelta

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Task, QuietDay


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> tuple[User, bool]:
    """Получить пользователя по telegram_id или создать нового.

    Возвращает (user, created) — объект пользователя и флаг создания.
    """
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user, False

    user = User(telegram_id=telegram_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Получить пользователя по telegram_id."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# --- Задачи ---

async def create_task(
    session: AsyncSession,
    user_id: int,
    title: str,
    scheduled_at: datetime | None = None,
    duration_min: int | None = None,
    category: str | None = None,
    description: str | None = None,
) -> Task:
    """Создать новую задачу."""
    # Убираем timezone — БД хранит naive datetime (UTC)
    if scheduled_at and scheduled_at.tzinfo is not None:
        scheduled_at = scheduled_at.replace(tzinfo=None)

    task = Task(
        user_id=user_id,
        title=title,
        scheduled_at=scheduled_at,
        duration_min=duration_min,
        category=category,
        description=description,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_tasks_by_date(session: AsyncSession, user_id: int, target_date: date) -> list[Task]:
    """Получить все задачи пользователя на указанную дату, отсортированные по времени."""
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    stmt = (
        select(Task)
        .where(
            and_(
                Task.user_id == user_id,
                Task.scheduled_at >= day_start,
                Task.scheduled_at <= day_end,
            )
        )
        .order_by(Task.scheduled_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_task_status(
    session: AsyncSession,
    task_id: int,
    status: str,
    completion_pct: int | None = None,
) -> Task | None:
    """Обновить статус задачи. Возвращает None если задача не найдена."""
    stmt = select(Task).where(Task.id == task_id)
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        return None

    task.status = status
    if completion_pct is not None:
        task.completion_pct = completion_pct

    await session.commit()
    await session.refresh(task)
    return task


async def get_calendar_data(
    session: AsyncSession,
    user_id: int,
    from_date: date,
    to_date: date,
) -> list[dict]:
    """Получить количество задач и флаги тихих дней для каждого дня диапазона.

    Возвращает список словарей:
    [{"date": "YYYY-MM-DD", "tasks_count": N, "is_quiet_day": bool}]
    """
    # Количество задач по дням
    day_start = datetime.combine(from_date, datetime.min.time())
    day_end = datetime.combine(to_date, datetime.max.time())

    tasks_stmt = (
        select(
            func.date(Task.scheduled_at).label("task_date"),
            func.count(Task.id).label("cnt"),
        )
        .where(
            and_(
                Task.user_id == user_id,
                Task.scheduled_at >= day_start,
                Task.scheduled_at <= day_end,
            )
        )
        .group_by(func.date(Task.scheduled_at))
    )
    tasks_result = await session.execute(tasks_stmt)
    tasks_by_date = {str(row.task_date): row.cnt for row in tasks_result}

    # Тихие дни: повторяющиеся (день недели) и конкретные даты
    quiet_stmt = select(QuietDay).where(
        and_(
            QuietDay.user_id == user_id,
            QuietDay.is_active == True,  # noqa: E712
        )
    )
    quiet_result = await session.execute(quiet_stmt)
    quiet_days = quiet_result.scalars().all()

    # Собрать множество тихих дат в диапазоне
    quiet_dates: set[str] = set()
    current = from_date
    while current <= to_date:
        for qd in quiet_days:
            if qd.specific_date and qd.specific_date == current:
                quiet_dates.add(str(current))
                break
            # day_of_week: 0=пн, 6=вс; weekday(): 0=пн, 6=вс — совпадают
            if qd.day_of_week is not None and qd.day_of_week == current.weekday():
                quiet_dates.add(str(current))
                break
        current += timedelta(days=1)

    # Формирование итогового списка
    result = []
    current = from_date
    while current <= to_date:
        date_str = str(current)
        result.append({
            "date": date_str,
            "tasks_count": tasks_by_date.get(date_str, 0),
            "is_quiet_day": date_str in quiet_dates,
        })
        current += timedelta(days=1)

    return result


async def update_task(
    session: AsyncSession,
    task_id: int,
    **kwargs,
) -> Task | None:
    """Обновить произвольные поля задачи."""
    stmt = select(Task).where(Task.id == task_id)
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        return None

    for key, value in kwargs.items():
        if hasattr(task, key):
            # Убираем timezone из datetime — БД хранит naive (UTC)
            if isinstance(value, datetime) and value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            setattr(task, key, value)

    await session.commit()
    await session.refresh(task)
    return task
