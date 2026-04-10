"""Вечерний дневник — запрос рефлексии в 21:00 UTC (по умолчанию).

НЕ отправляется в тихий день (для тихих дней — quiet_day_summary в 21:30).
Уважает настройки уведомлений: проверяет enabled для типа evening_reflection.
"""

import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from db.models import User

logger = logging.getLogger(__name__)

# Множество telegram_id, ожидающих ввода рефлексии (используется reflection.py)
_awaiting_reflection: set[int] = set()

_SKIP_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Пропустить ⏭", callback_data="reflect:skip")],
])


async def send_evening_reflection_request(bot: Bot, user: User) -> bool:
    """Отправить запрос вечерней рефлексии пользователю (без звука).

    Возвращает True если отправлено.
    """
    _awaiting_reflection.add(user.telegram_id)
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "🌙 <b>Вечерний дневник</b>\n\n"
                "Как прошёл день? Напиши пару слов — \n"
                "что получилось, что нет, что чувствуешь."
            ),
            parse_mode="HTML",
            disable_notification=True,
            reply_markup=_SKIP_KB,
        )
        logger.info("Вечерний дневник отправлен пользователю %d", user.telegram_id)
        return True
    except Exception as exc:
        _awaiting_reflection.discard(user.telegram_id)
        logger.error("Ошибка evening_reflection user=%d: %s", user.telegram_id, exc)
        return False


def is_awaiting_reflection(telegram_id: int) -> bool:
    """Ожидает ли пользователь ввода рефлексии."""
    return telegram_id in _awaiting_reflection


def clear_awaiting(telegram_id: int) -> None:
    """Снять флаг ожидания."""
    _awaiting_reflection.discard(telegram_id)
