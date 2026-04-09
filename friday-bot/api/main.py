"""Точка входа FastAPI-приложения."""

from fastapi import FastAPI


app = FastAPI(title="Friday Bot API", version="0.1.0")


@app.get("/health")
async def health():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
