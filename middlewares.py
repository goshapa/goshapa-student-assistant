"""Owner-only authorization middleware. Applied to every update."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

LOCK_MESSAGE = "🔒 Этот бот является личным и недоступен для вашего аккаунта."


class OwnerOnlyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")

        if user is not None and user.id != settings.owner_telegram_id:
            logger.warning("Blocked access from non-owner telegram_id=%s", user.id)
            if isinstance(event, Message):
                await event.answer(LOCK_MESSAGE)
            elif isinstance(event, CallbackQuery):
                await event.answer(LOCK_MESSAGE, show_alert=True)
            return None

        return await handler(event, data)
