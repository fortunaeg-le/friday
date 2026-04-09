"""Inline-клавиатуры для работы с задачами."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Выбор категории задачи
CATEGORIES = ["работа", "здоровье", "личное", "другое"]

category_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(text="💼 Работа", callback_data="cat:работа"),
     InlineKeyboardButton(text="❤️ Здоровье", callback_data="cat:здоровье")],
    [InlineKeyboardButton(text="👤 Личное", callback_data="cat:личное"),
     InlineKeyboardButton(text="📦 Другое", callback_data="cat:другое")],
])

# Пропуск необязательного шага
skip_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(text="Пропустить ⏭", callback_data="skip")],
])

# Пропуск длительности
skip_duration_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(text="Пропустить ⏭", callback_data="skip")],
])
