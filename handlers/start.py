"""/start, /help and the welcome flow."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from database import get_session
from database.models import User
from keyboards.main import main_menu_keyboard
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="start")

WELCOME_TEXT = (
    "👋 Welcome to Goshapa Student Assistant\n\n"
    "Я буду следить за твоими парами, Canvas assignments\n"
    "и дедлайнами, чтобы ты ничего не пропустил."
)

HELP_TEXT = (
    "🤖 Goshapa Student Assistant\n\n"
    "/today — расписание на сегодня\n"
    "/tomorrow — расписание на завтра\n"
    "/week — расписание на неделю\n"
    "/assignments — активные задания\n"
    "/deadlines — ближайшие дедлайны\n"
    "/sync — синхронизация с Canvas\n"
    "/settings — настройки\n"
    "/help — эта справка"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with get_session() as session:
        user = await session.get(User, message.from_user.id)
        if user is None:
            session.add(User(id=message.from_user.id))
            await session.commit()
            logger.info("Registered owner telegram_id=%s", message.from_user.id)

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())
