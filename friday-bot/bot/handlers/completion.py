"""Хендлер отметки выполнения задачи: Да / Частично / Не выполнил."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db.database import async_session
from db.crud import update_task_status

logger = logging.getLogger(__name__)

# Состояние FSM: ожидание процента выполнения
WAITING_PCT = 0


async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь нажал «Да, полностью»."""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(":")[2])
    async with async_session() as session:
        await update_task_status(session, task_id, status="done")

    await query.edit_message_text(
        f"{query.message.text}\n\n🎉 <b>Отлично! Задача выполнена.</b>",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def handle_partial_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь нажал «Частично» — запрашиваем процент."""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(":")[2])
    context.user_data["completion_task_id"] = task_id

    await query.edit_message_text(
        f"{query.message.text}\n\n🔸 <b>Частично.</b> Введи примерный % выполнения (0–100):",
        parse_mode="HTML",
    )
    return WAITING_PCT


async def handle_partial_pct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получили процент выполнения — сохраняем."""
    text = update.message.text.strip()
    if not text.isdigit() or not (0 <= int(text) <= 100):
        await update.message.reply_text("❌ Введи число от 0 до 100:")
        return WAITING_PCT

    pct = int(text)
    task_id = context.user_data.pop("completion_task_id", None)
    if not task_id:
        await update.message.reply_text("❌ Не удалось определить задачу. Попробуй ещё раз.")
        return ConversationHandler.END

    async with async_session() as session:
        await update_task_status(session, task_id, status="partial", completion_pct=pct)

    await update.message.reply_text(
        f"📊 Сохранено: <b>{pct}%</b> выполнено.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пользователь нажал «Не выполнил»."""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split(":")[2])
    async with async_session() as session:
        await update_task_status(session, task_id, status="skipped")

    await query.edit_message_text(
        f"{query.message.text}\n\n📝 Понял, задача отмечена как не выполненная.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("completion_task_id", None)
    return ConversationHandler.END


# ConversationHandler: partial начинается с callback, потом ожидает текст с %
completion_partial_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(handle_partial_start, pattern=r"^completion:partial:\d+$"),
    ],
    states={
        WAITING_PCT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_partial_pct),
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel, pattern=r"^cancel$")],
    per_message=False,
)

# Простые callback-хендлеры для done/skip (не требуют FSM)
completion_done_handler = CallbackQueryHandler(
    handle_done, pattern=r"^completion:done:\d+$"
)
completion_skip_handler = CallbackQueryHandler(
    handle_skip, pattern=r"^completion:skip:\d+$"
)
