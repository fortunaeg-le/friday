"""REST-эндпоинт для данных календаря (мини-календарь в Mini App)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.crud import get_calendar_data, get_user_by_telegram_id

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("")
async def get_calendar(
    from_date: date = Query(..., alias="from", description="Начало диапазона YYYY-MM-DD"),
    to_date: date = Query(..., alias="to", description="Конец диапазона YYYY-MM-DD"),
    telegram_id: int = Query(..., description="Telegram ID пользователя"),
    session: AsyncSession = Depends(get_session),
):
    """Получить количество задач и флаги тихих дней для диапазона дат.

    Возвращает список объектов:
    [{"date": "YYYY-MM-DD", "tasks_count": N, "is_quiet_day": bool}]
    """
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from должна быть ≤ to")

    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return await get_calendar_data(session, user.id, from_date, to_date)
