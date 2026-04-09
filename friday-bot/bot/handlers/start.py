"""Хендлер команды /start — регистрация пользователя и приветствие."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import CommandHandler, ContextTypes

from core.config import settings
from db.database import async_session
from db.crud import get_or_create_user

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка /start — создаёт пользователя в БД и отправляет приветствие."""
    tg_user = update.effective_user
    if tg_user is None:
        return

    # Регистрация / получение пользователя
    async with async_session() as session:
        user, created = await get_or_create_user(session, tg_user.id)

    if created:
        logger.info("Новый пользователь: telegram_id=%s", tg_user.id)

    # Кнопка открытия Mini App
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="📅 Открыть Пятницу",
            web_app=WebAppInfo(url=settings.mini_app_url),
        )]
    ]) if settings.mini_app_url else None

    greeting = (
        f"Привет, {tg_user.first_name}! 👋\n\n"
        "Я <b>Пятница</b> — твой персональный ежедневник.\n\n"
        "Что я умею:\n"
        "• 📅 Вести расписание\n"
        "• ⏰ Напоминать о задачах\n"
        "• 📊 Собирать статистику\n"
        "• 💡 Предлагать задачи в свободное время\n\n"
        "Нажми кнопку ниже, чтобы открыть ежедневник, "
        "или используй /add для быстрого добавления задачи."
    )

    await update.message.reply_text(
        text=greeting,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# Экспорт хендлера для регистрации в Application
start_handler = CommandHandler("start", start_command)
