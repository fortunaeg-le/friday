"""Обработка callback-кнопок рекомендаций в свободные окна."""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes

from db.database import async_session
from db.crud import (
    get_or_create_user,
    get_pending_subtasks_for_user,
    create_task,
)
from db.models import ProjectSubtask
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def _get_subtask(session, subtask_id: int) -> ProjectSubtask | None:
    result = await session.execute(
        select(ProjectSubtask).where(ProjectSubtask.id == subtask_id)
    )
    return result.scalar_one_or_none()


async def handle_suggestion_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«Начать» — создать задачу из подзадачи проекта на текущее время."""
    query = update.callback_query
    await query.answer()

    subtask_id = int(query.data.split(":")[2])

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        subtask = await _get_subtask(session, subtask_id)

        if subtask is None:
            await query.edit_message_text("❌ Подзадача не найдена.")
            return

        now = datetime.utcnow()
        task = await create_task(
            session,
            user_id=user.id,
            title=subtask.title,
            scheduled_at=now,
            duration_min=subtask.duration_min,
            category="другое",
        )
        # Связываем задачу с подзадачей проекта
        from sqlalchemy import update as sa_update
        from db.models import Task
        await session.execute(
            sa_update(Task)
            .where(Task.id == task.id)
            .values(subtask_of=subtask.id)
        )
        await session.commit()

    await query.edit_message_text(
        f"✅ Задача добавлена в расписание!\n\n"
        f"📝 <b>{subtask.title}</b>\n"
        f"🕐 Начало: {now.strftime('%H:%M')}",
        parse_mode="HTML",
    )


async def handle_suggestion_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«Отложить» — убрать кнопки, не создавать задачу."""
    query = update.callback_query
    await query.answer("Хорошо, напомню позже 👍")
    await query.edit_message_reply_markup(reply_markup=None)


async def handle_suggestion_another(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«Другую задачу» — предложить следующую pending подзадачу."""
    query = update.callback_query
    await query.answer()

    current_subtask_id = int(query.data.split(":")[2])

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        subtasks = await get_pending_subtasks_for_user(
            session, user.id, exclude_id=current_subtask_id
        )

    if not subtasks:
        await query.edit_message_text(
            "📭 Больше нет доступных подзадач.\n"
            "Создай новый проект командой /project"
        )
        return

    subtask = subtasks[0]
    dur_str = f"{subtask.duration_min} мин" if subtask.duration_min else "время не задано"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Начать", callback_data=f"suggestion:start:{subtask.id}")],
        [
            InlineKeyboardButton("⏭ Отложить", callback_data="suggestion:skip"),
            InlineKeyboardButton("🔄 Другую", callback_data=f"suggestion:another:{subtask.id}"),
        ],
    ])

    await query.edit_message_text(
        f"💡 <b>Как насчёт этой подзадачи?</b>\n\n"
        f"📝 <b>{subtask.title}</b>\n"
        f"⏱ {dur_str}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# Хендлеры для регистрации в Application
suggestion_start_handler = CallbackQueryHandler(
    handle_suggestion_start, pattern=r"^suggestion:start:\d+$"
)
suggestion_skip_handler = CallbackQueryHandler(
    handle_suggestion_skip, pattern=r"^suggestion:skip$"
)
suggestion_another_handler = CallbackQueryHandler(
    handle_suggestion_another, pattern=r"^suggestion:another:\d+$"
)
