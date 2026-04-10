"""FSM-хендлер создания проекта через бот: /project."""

import logging
from datetime import date, datetime

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db.database import async_session
from db.crud import get_or_create_user, create_project, add_subtask, get_projects, get_subtasks
from bot.keyboards.project_keyboards import add_subtask_keyboard, skip_deadline_keyboard

logger = logging.getLogger(__name__)

# Состояния FSM
PROJ_NAME, PROJ_DEADLINE, PROJ_SUBTASK = range(10, 13)


def _parse_deadline(text: str) -> date | None:
    """Парсинг дедлайна: DD.MM, DD.MM.YYYY, YYYY-MM-DD."""
    text = text.strip()
    today = date.today()
    for fmt in ("%d.%m.%Y", "%d.%m", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            if fmt == "%d.%m":
                parsed = parsed.replace(year=today.year)
            return parsed
        except ValueError:
            continue
    return None


async def project_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало: /project — запрос названия проекта."""
    await update.message.reply_text(
        "📁 <b>Создание нового проекта</b>\n\n"
        "Введи название проекта:",
        parse_mode="HTML",
    )
    return PROJ_NAME


async def project_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение названия, запрос дедлайна."""
    context.user_data["proj_title"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Введи дедлайн проекта (необязательно):\n"
        "<i>15.06, 15.06.2025, 2025-06-15</i>",
        parse_mode="HTML",
        reply_markup=skip_deadline_keyboard,
    )
    return PROJ_DEADLINE


async def project_deadline_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение дедлайна текстом, запрос первой подзадачи."""
    parsed = _parse_deadline(update.message.text)
    if parsed is None:
        await update.message.reply_text(
            "❌ Не удалось распознать дату. Попробуй ещё раз\n"
            "<i>или нажми «Пропустить»</i>",
            parse_mode="HTML",
            reply_markup=skip_deadline_keyboard,
        )
        return PROJ_DEADLINE

    context.user_data["proj_deadline"] = parsed
    return await _ask_first_subtask(update, context)


async def project_deadline_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск дедлайна."""
    query = update.callback_query
    await query.answer()
    context.user_data["proj_deadline"] = None
    # Имитируем update.message для единой функции
    context.user_data["_query"] = query
    return await _ask_first_subtask_query(query, context)


async def _ask_first_subtask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос первой подзадачи (через message)."""
    context.user_data.setdefault("proj_subtasks", [])
    await update.message.reply_text(
        "📝 Добавь первую подзадачу (или нажми «Готово» если подзадач нет):",
        reply_markup=add_subtask_keyboard,
    )
    return PROJ_SUBTASK


async def _ask_first_subtask_query(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос первой подзадачи (через callback query)."""
    context.user_data.setdefault("proj_subtasks", [])
    await query.edit_message_text(
        "📝 Добавь первую подзадачу (или нажми «Готово» если подзадач нет):",
        reply_markup=add_subtask_keyboard,
    )
    return PROJ_SUBTASK


async def project_subtask_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение текста подзадачи."""
    title = update.message.text.strip()
    subtasks: list = context.user_data.setdefault("proj_subtasks", [])
    subtasks.append(title)

    count = len(subtasks)
    await update.message.reply_text(
        f"✅ Подзадача {count} добавлена: <b>{title}</b>\n\n"
        "Добавь ещё одну или нажми «Готово»:",
        parse_mode="HTML",
        reply_markup=add_subtask_keyboard,
    )
    return PROJ_SUBTASK


async def project_add_subtask_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Кнопка «Добавить подзадачу» — просим ввести текст."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ Введи название подзадачи:")
    return PROJ_SUBTASK


async def project_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Кнопка «Готово» — сохраняем проект с подзадачами."""
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    title: str = ud.get("proj_title", "Без названия")
    deadline: date | None = ud.get("proj_deadline")
    subtasks: list[str] = ud.get("proj_subtasks", [])

    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        project = await create_project(
            session,
            user_id=user.id,
            title=title,
            deadline=deadline,
        )
        for idx, sub_title in enumerate(subtasks):
            await add_subtask(session, project_id=project.id, title=sub_title, order_index=idx)

    deadline_str = deadline.strftime("%d.%m.%Y") if deadline else "не указан"
    sub_list = "\n".join(f"  • {s}" for s in subtasks) if subtasks else "  — нет подзадач"

    await query.edit_message_text(
        f"✅ <b>Проект создан!</b>\n\n"
        f"📁 {title}\n"
        f"📅 Дедлайн: {deadline_str}\n\n"
        f"📝 Подзадачи:\n{sub_list}",
        parse_mode="HTML",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def project_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена создания проекта."""
    context.user_data.clear()
    await update.message.reply_text("❌ Создание проекта отменено.")
    return ConversationHandler.END


async def projects_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/projects — показать список активных проектов с подзадачами."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)
        projects = await get_projects(session, user.id)

    if not projects:
        await update.message.reply_text(
            "📁 У тебя пока нет активных проектов.\n"
            "Создай первый командой /project"
        )
        return

    lines = ["📁 <b>Активные проекты:</b>\n"]
    for p in projects:
        deadline_str = p.deadline.strftime("%d.%m.%Y") if p.deadline else "без дедлайна"
        total = len(p.subtasks)
        done = sum(1 for s in p.subtasks if s.status == "done")
        pct = int(done / total * 100) if total else 0
        bar = _progress_bar(pct)
        lines.append(f"<b>{p.title}</b> — {deadline_str}")
        lines.append(f"  {bar} {pct}% ({done}/{total})")
        if p.subtasks:
            for s in p.subtasks:
                icon = "✅" if s.status == "done" else ("⏭" if s.status == "skipped" else "⬜")
                lines.append(f"  {icon} {s.title}")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def _progress_bar(pct: int, length: int = 8) -> str:
    """Текстовый прогресс-бар."""
    filled = round(pct / 100 * length)
    return "█" * filled + "░" * (length - filled)


# ConversationHandler для регистрации в Application
project_handler = ConversationHandler(
    entry_points=[CommandHandler("project", project_start)],
    states={
        PROJ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, project_name)],
        PROJ_DEADLINE: [
            CallbackQueryHandler(project_deadline_skip, pattern="^proj:skip_deadline$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, project_deadline_text),
        ],
        PROJ_SUBTASK: [
            CallbackQueryHandler(project_add_subtask_prompt, pattern="^proj:add_subtask$"),
            CallbackQueryHandler(project_done, pattern="^proj:done$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, project_subtask_text),
        ],
    },
    fallbacks=[CommandHandler("cancel", project_cancel)],
)

# Простой хендлер списка проектов
projects_list_handler = CommandHandler("projects", projects_list)
