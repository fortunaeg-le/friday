"""FSM-хендлер вечернего дневника.

Перехватывает текст от пользователей, ожидающих ввода рефлексии,
и сохраняет его в daily_logs.reflection_text.
"""

import logging
from datetime import date

from sqlalchemy import select, and_
from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db.database import async_session
from db.crud import get_user_by_telegram_id
from db.models import DailyLog
from bot.notifications.evening_reflection import is_awaiting_reflection, clear_awaiting

logger = logging.getLogger(__name__)


async def _save_reflection(user_id: int, text: str | None) -> None:
    """Сохранить текст рефлексии в daily_logs."""
    today = date.today()
    async with async_session() as session:
        stmt = select(DailyLog).where(
            and_(DailyLog.user_id == user_id, DailyLog.log_date == today)
        )
        result = await session.execute(stmt)
        log = result.scalar_one_or_none()

        if log is None:
            log = DailyLog(
                user_id=user_id,
                log_date=today,
                is_quiet_day=False,
                reflection_text=text,
            )
            session.add(log)
        else:
            if text:
                log.reflection_text = text
        await session.commit()


async def handle_reflection_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перехватывает текст и сохраняет рефлексию."""
    tg_id = update.effective_user.id
    if not is_awaiting_reflection(tg_id):
        return

    clear_awaiting(tg_id)
    text = update.message.text.strip()

    async with async_session() as session:
        user = await get_user_by_telegram_id(session, tg_id)
    if user is None:
        return

    await _save_reflection(user.id, text)
    await update.message.reply_text(
        "✅ Записано. Спокойной ночи! 🌙",
    )
    logger.info("Рефлексия сохранена для user=%d", tg_id)


async def handle_reflection_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пользователь нажал «Пропустить»."""
    query = update.callback_query
    await query.answer("Хорошо, до завтра! 👋")
    clear_awaiting(update.effective_user.id)
    await query.edit_message_reply_markup(reply_markup=None)


# Хендлеры для регистрации в Application
reflection_text_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_reflection_text
)
reflection_skip_handler = CallbackQueryHandler(
    handle_reflection_skip, pattern=r"^reflect:skip$"
)
