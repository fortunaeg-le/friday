"""REST API настроек уведомлений."""

import logging
from typing import Any

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from db.database import async_session
from db.crud import get_or_create_user, get_notification_settings, update_notification_setting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class NotificationSettingResponse(BaseModel):
    type: str
    enabled: bool
    sound_enabled: bool
    remind_before_min: int | None


class NotificationSettingUpdate(BaseModel):
    enabled: bool | None = None
    sound_enabled: bool | None = None
    remind_before_min: int | None = None


@router.get("", response_model=list[NotificationSettingResponse])
async def get_settings(telegram_id: int = Query(...)):
    """Получить настройки уведомлений пользователя (с fallback на defaults)."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, telegram_id)
        settings = await get_notification_settings(session, user.id)
    return settings


@router.patch("/{ntype}", response_model=NotificationSettingResponse)
async def update_setting(
    ntype: str,
    body: NotificationSettingUpdate,
    telegram_id: int = Query(...),
):
    """Обновить настройку одного типа уведомления."""
    from db.crud import ALL_NOTIFICATION_TYPES
    if ntype not in ALL_NOTIFICATION_TYPES:
        raise HTTPException(status_code=404, detail="Unknown notification type")

    updates: dict[str, Any] = {}
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    if body.sound_enabled is not None:
        updates["sound_enabled"] = body.sound_enabled
    if body.remind_before_min is not None:
        updates["remind_before_min"] = body.remind_before_min

    async with async_session() as session:
        user, _ = await get_or_create_user(session, telegram_id)
        if updates:
            await update_notification_setting(session, user.id, ntype, **updates)
        settings = await get_notification_settings(session, user.id)

    s = next((x for x in settings if x["type"] == ntype), None)
    if s is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return s
