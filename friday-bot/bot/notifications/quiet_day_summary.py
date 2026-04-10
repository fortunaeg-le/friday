"""Вечерняя сводка тихого дня (21:30).

Шаг 1: запрос краткого текста от пользователя.
Шаг 2: автосводка (задачи сегодня + первые задачи завтра).
FSM: сохраняем ожидающих пользователей в памяти, перехватываем их сообщение.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import select, and_
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from db.database import async_session
from db.crud import get_tasks_by_date, get_user_by_telegram_id
from db.models import DailyLog, User

logger = logging.getLogger(__name__)

# telegram_id → True если ждём текст рефлексии
_awaiting_reflection: set[int] = set()

_SKIP_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Пропустить ⏭", callback_data="qd_summary:skip")],
])


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

async def _save_reflection(user: User, text: str | None) -> None:
    """Сохранить/обновить запись в daily_logs с is_quiet_day=True."""
    today = date.today()
    async with async_session() as session:
        stmt = select(DailyLog).where(
            and_(DailyLog.user_id == user.id, DailyLog.log_date == today)
        )
        result = await session.execute(stmt)
        log = result.scalar_one_or_none()

        if log is None:
            log = DailyLog(
                user_id=user.id,
                log_date=today,
                is_quiet_day=True,
                reflection_text=text,
            )
            session.add(log)
        else:
            log.is_quiet_day = True
            if text:
                log.reflection_text = text
        await session.commit()


async def _send_auto_summary(bot: Bot, user: User) -> None:
    """Автоматическая сводка после рефлексии — без звука."""
    today = date.today()
    tomorrow = today + timedelta(days=1)

    async with async_session() as session:
        today_tasks = await get_tasks_by_date(session, user.id, today)
        tomorrow_tasks = await get_tasks_by_date(session, user.id, tomorrow)

    planned = len(today_tasks)
    noun = "задача" if planned == 1 else "задач"
    lines = [
        "🌿 <b>Тихий день завершён.</b>",
        "",
        f"📋 Было запланировано: {planned} {noun}",
    ]
    if tomorrow_tasks:
        lines.append("Завтра тебя ждёт:")
        for t in tomorrow_tasks[:2]:
            ts = t.scheduled_at.strftime("%H:%M") if t.scheduled_at else "——"
            lines.append(f"  • {ts} {t.title}")

    await bot.send_message(
        chat_id=user.telegram_id,
        text="\n".join(lines),
        parse_mode="HTML",
        disable_notification=True,
    )


# ---------------------------------------------------------------------------
# Публичная функция — вызывается планировщиком
# ---------------------------------------------------------------------------

async def send_quiet_day_summary_request(bot: Bot, user: User) -> None:
    """Отправить запрос рефлексии в конце тихого дня (21:30) и поставить в ожидание."""
    _awaiting_reflection.add(user.telegram_id)
    await bot.send_message(
        chat_id=user.telegram_id,
        text=(
            "🌿 <b>Тихий день завершается.</b>\n\n"
            "Напиши коротко — что сегодня сделал, даже если немного."
        ),
        parse_mode="HTML",
        disable_notification=True,
        reply_markup=_SKIP_KB,
    )


# ---------------------------------------------------------------------------
# Хендлеры (регистрируются в Application)
# ---------------------------------------------------------------------------

async def handle_qd_summary_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перехватывает текст пользователя, если он ждёт рефлексии."""
    tg_id = update.effective_user.id
    if tg_id not in _awaiting_reflection:
        return  # не наш пользователь — пропускаем

    _awaiting_reflection.discard(tg_id)
    text = update.message.text.strip()

    async with async_session() as session:
        user = await get_user_by_telegram_id(session, tg_id)
    if user is None:
        return

    await _save_reflection(user, text)
    await update.message.reply_text("✅ Записано.")
    await _send_auto_summary(update.get_bot(), user)


async def handle_qd_summary_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пользователь нажал «Пропустить»."""
    query = update.callback_query
    await query.answer()
    tg_id = update.effective_user.id
    _awaiting_reflection.discard(tg_id)

    await query.edit_message_reply_markup(reply_markup=None)

    async with async_session() as session:
        user = await get_user_by_telegram_id(session, tg_id)
    if user is None:
        return

    await _save_reflection(user, None)
    await _send_auto_summary(update.get_bot(), user)


# Хендлеры для регистрации в Application
qd_summary_text_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_qd_summary_text
)
qd_summary_skip_handler = CallbackQueryHandler(
    handle_qd_summary_skip, pattern=r"^qd_summary:skip$"
)
