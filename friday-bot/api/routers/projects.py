"""REST API для проектов и подзадач."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session
from db.crud import (
    get_or_create_user,
    create_project,
    add_subtask,
    get_projects,
    get_subtasks,
    update_subtask_status,
    get_project_by_id,
    delete_project,
    update_project,
    update_subtask,
)
from api.schemas.projects import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    SubtaskCreate,
    SubtaskResponse,
    SubtaskStatusUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _get_session():
    async with async_session() as session:
        yield session


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    telegram_id: int = Query(...),
    status: str = Query("active"),
):
    """Получить список проектов пользователя."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, telegram_id)
        projects = await get_projects(session, user.id, status=status)
    return projects


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_new_project(
    body: ProjectCreate,
    telegram_id: int = Query(...),
):
    """Создать новый проект."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, telegram_id)
        project = await create_project(
            session,
            user_id=user.id,
            title=body.title,
            description=body.description,
            deadline=body.deadline,
        )
        # Перечитаем с подзадачами (пустой список на старте)
        project = await get_project_by_id(session, project.id)
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def patch_project(
    project_id: int,
    body: ProjectUpdate,
    telegram_id: int = Query(...),
):
    """Обновить проект (название, дедлайн, статус)."""
    async with async_session() as session:
        project = await get_project_by_id(session, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        user, _ = await get_or_create_user(session, telegram_id)
        if project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        updates = body.model_dump(exclude_unset=True, exclude_none=True)
        project = await update_project(session, project_id, **updates)
        project = await get_project_by_id(session, project_id)
    return project


@router.delete("/{project_id}", status_code=204)
async def remove_project(
    project_id: int,
    telegram_id: int = Query(...),
):
    """Удалить проект вместе с подзадачами."""
    async with async_session() as session:
        project = await get_project_by_id(session, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        user, _ = await get_or_create_user(session, telegram_id)
        if project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        ok = await delete_project(session, project_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/subtasks", response_model=list[SubtaskResponse])
async def list_subtasks(project_id: int, telegram_id: int = Query(...)):
    """Получить подзадачи проекта."""
    async with async_session() as session:
        project = await get_project_by_id(session, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        user, _ = await get_or_create_user(session, telegram_id)
        if project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        subtasks = await get_subtasks(session, project_id)
    return subtasks


@router.post("/{project_id}/subtasks", response_model=SubtaskResponse, status_code=201)
async def create_subtask(
    project_id: int,
    body: SubtaskCreate,
    telegram_id: int = Query(...),
):
    """Добавить подзадачу к проекту."""
    async with async_session() as session:
        project = await get_project_by_id(session, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        user, _ = await get_or_create_user(session, telegram_id)
        if project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        subtask = await add_subtask(
            session,
            project_id=project_id,
            title=body.title,
            duration_min=body.duration_min,
            order_index=body.order_index,
        )
    return subtask


@router.patch("/{project_id}/subtasks/{subtask_id}", response_model=SubtaskResponse)
async def patch_subtask(
    project_id: int,
    subtask_id: int,
    body: SubtaskStatusUpdate,
    telegram_id: int = Query(...),
):
    """Обновить подзадачу (статус и/или название)."""
    if body.status and body.status not in ("pending", "done", "skipped"):
        raise HTTPException(status_code=422, detail="Invalid status")
    async with async_session() as session:
        project = await get_project_by_id(session, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        user, _ = await get_or_create_user(session, telegram_id)
        if project.user_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        updates = body.model_dump(exclude_unset=True, exclude_none=True)
        subtask = await update_subtask(session, subtask_id, **updates)
        if subtask is None:
            raise HTTPException(status_code=404, detail="Subtask not found")
    return subtask
