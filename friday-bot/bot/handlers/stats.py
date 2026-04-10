"""Хендлер команды /stats — краткая статистика с кнопкой открытия Mini App."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CommandHandler, ContextTypes

from core.config import settings
from db.database import async_session
from db.crud import get_or_create_user
from bot.notifications.stats_report import build_stats_message, _webapp_button

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — отправить краткий отчёт за текущую неделю."""
    async with async_session() as session:
        user, _ = await get_or_create_user(session, update.effective_user.id)

    text = await build_stats_message(user, "week")
    keyboard = _webapp_button()

    await update.message.reply_text(
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


stats_handler = CommandHandler("stats", stats_command)
