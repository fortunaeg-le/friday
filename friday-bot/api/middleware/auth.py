"""Middleware для верификации initData из Telegram Mini App (HMAC-SHA256)."""

import hashlib
import hmac
import logging
import urllib.parse
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings

logger = logging.getLogger(__name__)


def verify_init_data(init_data: str, bot_token: str) -> bool:
    """Проверить подпись initData из Telegram Mini App.

    Алгоритм по документации Telegram:
    1. Разобрать строку как URL query string
    2. Извлечь поле hash, остальные поля отсортировать и собрать в строку key=value\\n...
    3. Ключ = HMAC-SHA256("WebAppData", bot_token)
    4. Сравнить HMAC-SHA256(data_check_string, secret_key) с полем hash
    """
    try:
        params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.pop("hash", None)
        if not received_hash:
            return False

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )

        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        computed_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_hash, received_hash)
    except Exception as exc:
        logger.warning("Ошибка верификации initData: %s", exc)
        return False


class TelegramAuthMiddleware(BaseHTTPMiddleware):
    """Проверяет заголовок X-Telegram-Init-Data для всех запросов /api/*.

    В режиме debug (settings.debug=True) или при пустом заголовке — пропускает.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # В debug-режиме верификация отключена
        if settings.debug:
            return await call_next(request)

        init_data = request.headers.get("X-Telegram-Init-Data", "")

        # Пустой заголовок — пропускаем (запросы без Mini App контекста)
        if not init_data:
            return await call_next(request)

        if not verify_init_data(init_data, settings.bot_token):
            logger.warning(
                "Невалидный initData от %s %s",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return Response(content="Unauthorized", status_code=401)

        return await call_next(request)
