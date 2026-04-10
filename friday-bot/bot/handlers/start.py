"""Хендлер команды /start — регистрация пользователя и приветствие."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import CommandHandler, ContextTypes

from core.config import settings
from db.database import async_session
from db.crud import get_or_create_user

logger = logging.getLogger(__name__)

# Допустимые вкладки Mini App для deep link
_VALID_TABS = {"schedule", "stats", "projects", "settings"}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка /start — создаёт пользователя в БД и отправляет приветствие.

    Deep link: /start <tab> открывает Mini App на указанной вкладке
    (schedule | stats | projects | settings).
    """
    tg_user = update.effective_user
    if tg_user is None:
        return

    # Регистрация / получение пользователя
    async with async_session() as session:
        user, created = await get_or_create_user(session, tg_user.id)

    if created:
        logger.info("Новый пользователь: telegram_id=%s", tg_user.id)

    # Определяем вкладку из deep link параметра
    start_param = context.args[0] if context.args else None
    tab = start_param if start_param in _VALID_TABS else None

    # Формируем URL Mini App (с параметром startapp для deep link)
    if settings.mini_app_url:
        app_url = f"{settings.mini_app_url}?startapp={tab}" if tab else settings.mini_app_url
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text="📅 Открыть Пятницу",
                web_app=WebAppInfo(url=app_url),
            )]
        ])
    else:
        keyboard = None

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
