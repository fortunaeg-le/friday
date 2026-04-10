"""REST-эндпоинты для задач (Mini App)."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.crud import (
    create_task, get_tasks_by_date, update_task,
    get_user_by_telegram_id, ensure_task_reminder,
    delete_task, get_partial_tasks_for_user,
)
from api.schemas.tasks import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    date: date = Query(..., description="Дата в формате YYYY-MM-DD"),
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    session: AsyncSession = Depends(get_session),
):
    """Получить задачи пользователя на указанную дату."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    tasks = await get_tasks_by_date(session, user.id, date)
    return tasks


@router.post("", response_model=TaskResponse, status_code=201)
async def add_task(
    body: TaskCreate,
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    session: AsyncSession = Depends(get_session),
):
    """Создать новую задачу."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    task = await create_task(
        session,
        user_id=user.id,
        title=body.title,
        scheduled_at=body.scheduled_at,
        task_date=body.task_date,
        duration_min=body.duration_min,
        category=body.category,
        description=body.description,
    )
    # Автоматически создать напоминание
    await ensure_task_reminder(session, task)
    return task


@router.get("/partial", response_model=list[TaskResponse])
async def list_partial_tasks(
    telegram_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Получить частично выполненные задачи пользователя."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return await get_partial_tasks_for_user(session, user.id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def patch_task(
    task_id: int,
    body: TaskUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Обновить задачу (частичное обновление)."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")

    task = await update_task(session, task_id, **updates)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Не пересоздавать напоминание если задача уже выполнена
    if task.status not in ("done", "skipped"):
        await ensure_task_reminder(session, task)
    return task


@router.delete("/{task_id}", status_code=204)
async def remove_task(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Удалить задачу."""
    ok = await delete_task(session, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Задача не найдена")
