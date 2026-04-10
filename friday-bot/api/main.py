"""Точка входа FastAPI-приложения с интеграцией Telegram-бота."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update

from core.config import settings
from bot.app import create_bot_app
from bot.scheduler import setup_scheduler
from api.routers.health import router as health_router
from api.routers.tasks import router as tasks_router
from api.routers.calendar import router as calendar_router
from api.routers.projects import router as projects_router
from api.routers.stats import router as stats_router
from api.routers.settings import router as settings_router

logger = logging.getLogger(__name__)

# Глобальные ссылки
bot_app = None
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown — инициализация и остановка бота и планировщика."""
    global bot_app, scheduler

    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Инициализация бота
    bot_app = create_bot_app()
    await bot_app.initialize()
    await bot_app.start()

    # Установка webhook
    webhook_url = f"{settings.webhook_url}"
    await bot_app.bot.set_webhook(
        url=webhook_url,
        secret_token=settings.webhook_secret or None,
    )
    logger.info("Webhook установлен: %s", webhook_url)

    # Запуск планировщика
    scheduler = setup_scheduler(bot_app)
    scheduler.start()
    logger.info("Планировщик запущен")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Планировщик остановлен")
    await bot_app.stop()
    await bot_app.shutdown()
    logger.info("Бот остановлен")


app = FastAPI(title="Friday Bot API", version="0.1.0", lifespan=lifespan)

# Роутеры
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(calendar_router)
app.include_router(projects_router)
app.include_router(stats_router)
app.include_router(settings_router)


@app.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Приём обновлений от Telegram через webhook."""
    # Проверка секретного токена
    if settings.webhook_secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != settings.webhook_secret:
            return Response(status_code=403)

    # Обработка update
    data = await request.json()
    update = Update.de_json(data=data, bot=bot_app.bot)
    await bot_app.process_update(update)

    return Response(status_code=200)
