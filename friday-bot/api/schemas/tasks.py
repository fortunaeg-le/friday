"""Pydantic-схемы для задач (запросы/ответы API)."""

from datetime import datetime
from pydantic import BaseModel


class TaskCreate(BaseModel):
    """Создание задачи."""
    title: str
    scheduled_at: datetime | None = None
    duration_min: int | None = None
    category: str | None = None
    description: str | None = None


class TaskUpdate(BaseModel):
    """Обновление задачи (все поля опциональны)."""
    title: str | None = None
    scheduled_at: datetime | None = None
    duration_min: int | None = None
    category: str | None = None
    description: str | None = None
    status: str | None = None
    completion_pct: int | None = None


class TaskResponse(BaseModel):
    """Ответ с данными задачи."""
    id: int
    user_id: int
    title: str
    description: str | None = None
    scheduled_at: datetime | None = None
    duration_min: int | None = None
    category: str | None = None
    status: str
    completion_pct: int | None = None
    project_subtask_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
