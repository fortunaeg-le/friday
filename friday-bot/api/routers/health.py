"""Health-check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
