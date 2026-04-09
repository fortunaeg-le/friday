"""FSM-хендлер добавления задачи через бот: /add."""

import logging
from datetime import datetime, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db.database import async_session
from db.crud import get_or_create_user, create_task, ensure_task_reminder
from bot.keyboards.task_keyboards import category_keyboard, skip_duration_keyboard

logger = logging.getLogger(__name__)

# Состояния FSM
DATE, TIME, TITLE, DURATION, CATEGORY = range(5)


def _parse_date(text: str) -> date | None:
    """Парсинг даты: сегодня, завтра, ДД.ММ, ДД.ММ.ГГГГ."""
    text = text.strip().lower()
    today = date.today()

    if text in ("сегодня", "today"):
        return today
    if text in ("завтра", "tomorrow"):
        from datetime import timedelta
        return today + timedelta(days=1)

    for fmt in ("%d.%m.%Y", "%d.%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            # Если год не указан — берём текущий
            if fmt == "%d.%m":
                parsed = parsed.replace(year=today.year)
            return parsed
        except ValueError:
            continue
    return None


def _parse_time(text: str) -> tuple[int, int] | None:
    """Парсинг времени: 9, 9:00, 09:00, 900, 1430."""
    text = text.strip().replace(".", ":").replace("-", ":")

    # Формат HH:MM
    if ":" in text:
        parts = text.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
        return None

    if not text.isdigit():
        return None

    num = int(text)
    # Однозначное или двузначное число — часы
    if num <= 23:
        return num, 0
    # Трёхзначное: 930 → 9:30
    if 100 <= num <= 959:
        return num // 100, num % 100
    # Четырёхзначное: 1430 → 14:30
    if 1000 <= num <= 2359:
        h, m = num // 100, num % 100
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    return None


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало: /add — запрос даты."""
    await update.message.reply_text(
        "📅 Введи дату задачи:\n"
        "<i>сегодня, завтра, 15.04, 15.04.2025</i>",
        parse_mode="HTML",
    )
    return DATE


async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение даты, запрос времени."""
    parsed = _parse_date(update.message.text)
    if parsed is None:
        await update.message.reply_text("❌ Не удалось распознать дату. Попробуй ещё раз:")
        return DATE

    context.user_data["task_date"] = parsed
    await update.message.reply_text(
        "⏰ Введи время:\n"
        "<i>9, 9:00, 09:00, 1430</i>",
        parse_mode="HTML",
    )
    return TIME


async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение времени, запрос названия."""
    parsed = _parse_time(update.message.text)
    if parsed is None:
        await update.message.reply_text("❌ Не удалось распознать время. Попробуй ещё раз:")
        return TIME

    context.user_data["task_hour"] = parsed[0]
    context.user_data["task_minute"] = parsed[1]
    await update.message.reply_text("✏️ Введи название задачи:")
    return TITLE


async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение названия, запрос длительности."""
    context.user_data["task_title"] = update.message.text.strip()
    await update.message.reply_text(
        "⏱ Примерная длительность в минутах (необязательно):",
        reply_markup=skip_duration_keyboard,
    )
    return DURATION


async def add_duration_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение длительности текстом, запрос категории."""
    text = update.message.text.strip()
    if text.isdigit() and int(text) > 0:
        context.user_data["task_duration"] = int(text)
    else:
        await update.message.reply_text("❌ Введи число минут или нажми «Пропустить»:")
        return DURATION

    await update.message.reply_text("📂 Выбери категорию:", reply_markup=category_keyboard)
    return CATEGORY


async def add_duration_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск длительности."""
    query = update.callback_query
    await query.answer()
    context.user_data["task_duration"] = None
    await query.edit_message_text("📂 Выбери категорию:", reply_markup=category_keyboard)
    return CATEGORY


async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение категории, сохранение задачи."""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat:", "")
    ud = context.user_data

    # Собираем scheduled_at
    task_date = ud["task_date"]
    scheduled_at = datetime(
        task_date.year, task_date.month, task_date.day,
        ud["task_hour"], ud["task_minute"],
    )

    # Сохранение в БД
    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        task = await create_task(
            session,
            user_id=user.id,
            title=ud["task_title"],
            scheduled_at=scheduled_at,
            duration_min=ud.get("task_duration"),
            category=category,
        )
        # Автоматически создать напоминание
        await ensure_task_reminder(session, task)

    time_str = scheduled_at.strftime("%H:%M")
    dur_str = f", {task.duration_min} мин" if task.duration_min else ""
    await query.edit_message_text(
        f"✅ Задача добавлена!\n\n"
        f"📅 {task_date.strftime('%d.%m.%Y')} в {time_str}\n"
        f"📝 {task.title}\n"
        f"📂 {category}{dur_str}",
        parse_mode="HTML",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена добавления задачи."""
    context.user_data.clear()
    await update.message.reply_text("❌ Добавление задачи отменено.")
    return ConversationHandler.END


# ConversationHandler для регистрации в Application
add_task_handler = ConversationHandler(
    entry_points=[CommandHandler("add", add_start)],
    states={
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_time)],
        TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
        DURATION: [
            CallbackQueryHandler(add_duration_skip, pattern="^skip$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_duration_text),
        ],
        CATEGORY: [CallbackQueryHandler(add_category, pattern="^cat:")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
