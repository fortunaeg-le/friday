"""Хендлер настроек уведомлений: /settings.

Меню через inline-кнопки:
- список типов уведомлений с иконками вкл/выкл
- для каждого: вкл/выкл, звук/без, remind_before_min (для task_reminder)
- fallback на notification_defaults при NULL
"""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db.database import async_session
from db.crud import get_or_create_user, get_notification_settings, update_notification_setting

logger = logging.getLogger(__name__)

# Состояние FSM для ввода remind_before_min
SETTINGS_REMIND_MIN = 70

# Человекочитаемые имена типов
TYPE_LABELS = {
    "morning_summary":   "🌅 Утренняя сводка",
    "task_reminder":     "⏰ Напоминания о задачах",
    "completion_check":  "✅ Проверки выполнения",
    "window_suggestion": "💡 Рекомендации в окна",
    "weekly_report":     "📊 Еженедельный отчёт",
    "monthly_report":    "📅 Ежемесячный отчёт",
    "evening_reflection":"🌙 Вечерний дневник",
    "quiet_day_summary": "🌿 Сводка тихого дня",
}


def _settings_keyboard(settings: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура главного меню настроек."""
    rows = []
    for s in settings:
        label = TYPE_LABELS.get(s["type"], s["type"])
        icon = "🔔" if s["enabled"] else "🔕"
        rows.append([
            InlineKeyboardButton(
                f"{icon} {label}",
                callback_data=f"settings:open:{s['type']}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def _type_keyboard(s: dict) -> InlineKeyboardMarkup:
    """Клавиатура настроек одного типа уведомления."""
    ntype = s["type"]
    toggle_label = "🔕 Выключить" if s["enabled"] else "🔔 Включить"
    sound_label = "🔇 Без звука" if s["sound_enabled"] else "🔊 Со звуком"

    rows = [
        [InlineKeyboardButton(toggle_label, callback_data=f"settings:toggle:{ntype}")],
        [InlineKeyboardButton(sound_label, callback_data=f"settings:sound:{ntype}")],
    ]
    if ntype == "task_reminder":
        cur = s.get("remind_before_min") or 15
        rows.append([
            InlineKeyboardButton(
                f"⏱ Напомнить за {cur} мин",
                callback_data=f"settings:setmin:{ntype}",
            )
        ])
    rows.append([InlineKeyboardButton("← Назад", callback_data="settings:back")])
    return InlineKeyboardMarkup(rows)


async def _main_menu_text(settings: list[dict]) -> str:
    lines = ["⚙️ <b>Настройки уведомлений</b>\n"]
    for s in settings:
        label = TYPE_LABELS.get(s["type"], s["type"])
        status = "вкл" if s["enabled"] else "выкл"
        lines.append(f"• {label} — <i>{status}</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Хендлеры
# ---------------------------------------------------------------------------

async def settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/settings — главное меню."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        settings = await get_notification_settings(session, user.id)

    text = await _main_menu_text(settings)
    keyboard = _settings_keyboard(settings)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    return ConversationHandler.END


async def handle_settings_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: открыть настройки конкретного типа."""
    query = update.callback_query
    await query.answer()
    ntype = query.data.split(":")[2]

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        settings = await get_notification_settings(session, user.id)

    s = next((x for x in settings if x["type"] == ntype), None)
    if s is None:
        await query.answer("Тип не найден", show_alert=True)
        return

    label = TYPE_LABELS.get(ntype, ntype)
    text = (
        f"⚙️ <b>{label}</b>\n\n"
        f"Статус: {'включено' if s['enabled'] else 'выключено'}\n"
        f"Звук: {'да' if s['sound_enabled'] else 'нет'}"
    )
    if ntype == "task_reminder":
        text += f"\nНапоминание за: {s.get('remind_before_min') or 15} мин"

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=_type_keyboard(s))


async def handle_settings_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: переключить enabled."""
    query = update.callback_query
    await query.answer()
    ntype = query.data.split(":")[2]

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        settings = await get_notification_settings(session, user.id)
        s = next(x for x in settings if x["type"] == ntype)
        await update_notification_setting(session, user.id, ntype, enabled=not s["enabled"])
        settings = await get_notification_settings(session, user.id)

    s = next(x for x in settings if x["type"] == ntype)
    label = TYPE_LABELS.get(ntype, ntype)
    text = (
        f"⚙️ <b>{label}</b>\n\n"
        f"Статус: {'включено' if s['enabled'] else 'выключено'}\n"
        f"Звук: {'да' if s['sound_enabled'] else 'нет'}"
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=_type_keyboard(s))


async def handle_settings_sound(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: переключить sound_enabled."""
    query = update.callback_query
    await query.answer()
    ntype = query.data.split(":")[2]

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        settings = await get_notification_settings(session, user.id)
        s = next(x for x in settings if x["type"] == ntype)
        await update_notification_setting(session, user.id, ntype, sound_enabled=not s["sound_enabled"])
        settings = await get_notification_settings(session, user.id)

    s = next(x for x in settings if x["type"] == ntype)
    label = TYPE_LABELS.get(ntype, ntype)
    text = (
        f"⚙️ <b>{label}</b>\n\n"
        f"Статус: {'включено' if s['enabled'] else 'выключено'}\n"
        f"Звук: {'да' if s['sound_enabled'] else 'нет'}"
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=_type_keyboard(s))


async def handle_settings_setmin_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback: запросить кол-во минут для task_reminder."""
    query = update.callback_query
    await query.answer()
    context.user_data["settings_remind_type"] = "task_reminder"
    await query.edit_message_text(
        "⏱ Введи, за сколько минут присылать напоминание (например: 10, 15, 30):"
    )
    return SETTINGS_REMIND_MIN


async def handle_settings_min_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получить количество минут и сохранить."""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Введи положительное число минут:")
        return SETTINGS_REMIND_MIN

    minutes = int(text)
    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        await update_notification_setting(session, user.id, "task_reminder", remind_before_min=minutes)
        settings = await get_notification_settings(session, user.id)

    text_menu = await _main_menu_text(settings)
    keyboard = _settings_keyboard(settings)
    await update.message.reply_text(
        f"✅ Буду напоминать за {minutes} мин.\n\n{text_menu}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def handle_settings_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: вернуться в главное меню настроек."""
    query = update.callback_query
    await query.answer()

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        settings = await get_notification_settings(session, user.id)

    text = await _main_menu_text(settings)
    keyboard = _settings_keyboard(settings)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ConversationHandler для ввода remind_before_min
settings_handler = ConversationHandler(
    entry_points=[CommandHandler("settings", settings_start)],
    states={
        SETTINGS_REMIND_MIN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_settings_min_input),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_settings)],
)

# Callback-хендлеры — регистрировать отдельно
settings_open_handler = CallbackQueryHandler(handle_settings_open, pattern=r"^settings:open:")
settings_toggle_handler = CallbackQueryHandler(handle_settings_toggle, pattern=r"^settings:toggle:")
settings_sound_handler = CallbackQueryHandler(handle_settings_sound, pattern=r"^settings:sound:")
settings_setmin_handler = CallbackQueryHandler(handle_settings_setmin_prompt, pattern=r"^settings:setmin:")
settings_back_handler = CallbackQueryHandler(handle_settings_back, pattern=r"^settings:back$")
