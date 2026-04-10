"""Inline-клавиатуры для работы с проектами."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Кнопки при добавлении подзадач в проект
add_subtask_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(text="➕ Добавить подзадачу", callback_data="proj:add_subtask")],
    [InlineKeyboardButton(text="✅ Готово", callback_data="proj:done")],
])

# Кнопка пропуска дедлайна
skip_deadline_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(text="Пропустить ⏭", callback_data="proj:skip_deadline")],
])


def project_manage_keyboard(project_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления конкретным проектом."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="➕ Добавить подзадачу", callback_data=f"proj:subtask:{project_id}")],
        [InlineKeyboardButton(text="✅ Завершить проект", callback_data=f"proj:complete:{project_id}")],
        [InlineKeyboardButton(text="🗄 В архив", callback_data=f"proj:archive:{project_id}")],
    ])


def subtask_status_keyboard(subtask_id: int) -> InlineKeyboardMarkup:
    """Клавиатура смены статуса подзадачи."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="✅ Выполнена", callback_data=f"sub:done:{subtask_id}")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"sub:skip:{subtask_id}")],
    ])
