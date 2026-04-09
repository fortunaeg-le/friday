"""CRUD-операции с базой данных."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


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
