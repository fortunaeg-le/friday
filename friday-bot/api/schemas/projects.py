"""Pydantic-схемы для проектов и подзадач."""

from datetime import date, datetime

from pydantic import BaseModel


class SubtaskCreate(BaseModel):
    title: str
    duration_min: int | None = None
    order_index: int = 0


class SubtaskResponse(BaseModel):
    id: int
    project_id: int
    title: str
    duration_min: int | None
    status: str
    order_index: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    deadline: date | None = None


class ProjectResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: str | None
    deadline: date | None
    status: str
    created_at: datetime
    subtasks: list[SubtaskResponse] = []

    model_config = {"from_attributes": True}


class SubtaskStatusUpdate(BaseModel):
    status: str  # pending | done | skipped
