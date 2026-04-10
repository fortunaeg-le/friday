"""Формирование и отправка статистических отчётов (еженедельный / месячный / /stats)."""

import logging
from datetime import date

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from core.config import settings
from core.stats import (
    calc_completion_rate,
    calc_streak,
    calc_trend,
    period_bounds,
)
from db.database import async_session
from db.models import User

logger = logging.getLogger(__name__)


def _webapp_button(label: str = "Открыть в Пятнице") -> InlineKeyboardMarkup | None:
    """Кнопка deep link на вкладку статистики Mini App."""
    if not settings.mini_app_url:
        return None
    url = f"{settings.mini_app_url}?startapp=stats"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"📊 {label}", web_app=WebAppInfo(url=url))]
    ])


async def build_stats_message(user: User, period_type: str) -> str:
    """Сформировать краткое сообщение статистики для пользователя.

    period_type: "week" | "month"
    """
    today = date.today()
    async with async_session() as session:
        start, end = period_bounds(period_type, today)
        rate = await calc_completion_rate(session, user.id, start, end)
        trend = await calc_trend(session, user.id, period_type, start)
        streak = await calc_streak(session, user.id)

        # Подсчёт абсолютных чисел для сообщения
        from db.crud import get_tasks_by_date
        from datetime import timedelta
        from core.stats import _tasks_in_range, _effective_completion
        tasks = await _tasks_in_range(session, user.id, start, end)

    total = len(tasks)
    done_eff = sum(_effective_completion(t) for t in tasks)
    done_int = round(done_eff)
    pct = round(rate * 100)

    period_label = "недели" if period_type == "week" else "месяца"
    trend_sign = "+" if trend >= 0 else ""
    trend_str = f"📈 {trend_sign}{trend}% к прошлому периоду"
    if trend == 0:
        trend_str = "➡️ Без изменений к прошлому периоду"

    lines = [
        f"📊 <b>Итоги {period_label}</b>",
        "",
        f"✅ Выполнено: {done_int} из {total} задач — {pct}%",
        trend_str,
        f"🔥 Серия: {streak} дн. подряд",
        "",
        "Посмотреть детали →",
    ]
    return "\n".join(lines)


async def send_stats_report(bot: Bot, user: User, period_type: str) -> bool:
    """Отправить статистический отчёт пользователю.

    Возвращает True если отправлено.
    """
    try:
        text = await build_stats_message(user, period_type)
        keyboard = _webapp_button()
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return True
    except Exception as exc:
        logger.error("Ошибка stats_report user=%d: %s", user.telegram_id, exc)
        return False
