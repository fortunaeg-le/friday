"""Async engine и фабрика сессий для SQLAlchemy."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

# Async engine — подключение к PostgreSQL через asyncpg
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

# Фабрика async-сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Dependency для FastAPI — выдаёт сессию и закрывает после запроса."""
    async with async_session() as session:
        yield session
