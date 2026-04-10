"""Хендлер настройки тихих дней: /quietday.

Меню через inline-кнопки: выбор дней недели и конкретных дат.
"""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db.database import async_session
from db.crud import get_or_create_user, get_quiet_days, set_quiet_day

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Состояние FSM для ввода конкретной даты
QD_DATE_INPUT = 50


async def _build_menu(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Собрать текст + клавиатуру меню тихих дней."""
    async with async_session() as session:
        quiet_days = await get_quiet_days(session, user_id)

    active_weekdays = {qd.day_of_week for qd in quiet_days if qd.day_of_week is not None}
    active_dates = {qd.specific_date for qd in quiet_days if qd.specific_date is not None}

    # Кнопки дней недели (2 ряда × 4 и 3)
    wd_row1 = [
        InlineKeyboardButton(
            text=f"{'✅ ' if i in active_weekdays else ''}{WEEKDAY_NAMES[i]}",
            callback_data=f"qd:wd:{i}",
        )
        for i in range(4)
    ]
    wd_row2 = [
        InlineKeyboardButton(
            text=f"{'✅ ' if i in active_weekdays else ''}{WEEKDAY_NAMES[i]}",
            callback_data=f"qd:wd:{i}",
        )
        for i in range(4, 7)
    ]

    keyboard = InlineKeyboardMarkup([
        wd_row1,
        wd_row2,
        [InlineKeyboardButton("📅 Добавить конкретную дату", callback_data="qd:add_date")],
    ])

    lines = ["🌿 <b>Тихие дни</b>\n"]
    if not quiet_days:
        lines.append("Тихих дней нет. Нажми на день недели, чтобы добавить.")
    else:
        if active_weekdays:
            wds = ", ".join(WEEKDAY_NAMES[i] for i in sorted(active_weekdays))
            lines.append(f"Дни недели: {wds}")
        if active_dates:
            dates_str = ", ".join(d.strftime("%d.%m.%Y") for d in sorted(active_dates))
            lines.append(f"Даты: {dates_str}")
    lines.append("\nНажми на кнопку, чтобы включить/выключить.")

    return "\n".join(lines), keyboard


async def quietday_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/quietday — показать меню тихих дней."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
    text, keyboard = await _build_menu(user.id)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    return ConversationHandler.END


async def handle_qd_weekday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: переключить день недели."""
    query = update.callback_query
    await query.answer()
    day_of_week = int(query.data.split(":")[2])

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        _, is_active = await set_quiet_day(session, user.id, day_of_week=day_of_week)
        text, keyboard = await _build_menu(user.id)

    status = "добавлен" if is_active else "убран"
    await query.answer(f"{WEEKDAY_NAMES[day_of_week]} {status}", show_alert=False)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handle_qd_add_date_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: запросить конкретную дату."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📅 Введи дату в формате <b>ДД.ММ.ГГГГ</b> или <b>ДД.ММ</b>:\n"
        "<i>Например: 25.12 или 25.12.2025</i>",
        parse_mode="HTML",
    )
    return QD_DATE_INPUT


async def handle_qd_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить и сохранить конкретную дату тихого дня."""
    text = update.message.text.strip()
    today = datetime.today()
    specific_date = None

    for fmt in ("%d.%m.%Y", "%d.%m"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            if fmt == "%d.%m":
                parsed = parsed.replace(year=today.year)
            specific_date = parsed
            break
        except ValueError:
            continue

    if specific_date is None:
        await update.message.reply_text(
            "❌ Не удалось распознать дату. Введи в формате ДД.ММ.ГГГГ или ДД.ММ:"
        )
        return QD_DATE_INPUT

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        _, is_active = await set_quiet_day(session, user.id, specific_date=specific_date)
        text_menu, keyboard = await _build_menu(user.id)

    status = "добавлена" if is_active else "убрана"
    await update.message.reply_text(
        f"✅ Дата {specific_date.strftime('%d.%m.%Y')} {status}.\n\n{text_menu}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def cancel_qd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ConversationHandler для ввода даты
quiet_days_handler = ConversationHandler(
    entry_points=[CommandHandler("quietday", quietday_start)],
    states={
        QD_DATE_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_qd_date_input),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_qd)],
)

# Callback-хендлеры — регистрировать отдельно (вне conversation)
qd_weekday_handler = CallbackQueryHandler(handle_qd_weekday, pattern=r"^qd:wd:\d+$")
qd_add_date_handler = CallbackQueryHandler(handle_qd_add_date_prompt, pattern=r"^qd:add_date$")
