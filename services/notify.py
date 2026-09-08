"""Sends messages to the bot owner, optionally with a cached course banner."""
from __future__ import annotations

from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Course
from utils.logger import get_logger

logger = get_logger(__name__)


async def send_with_optional_banner(
    bot: Bot,
    session: AsyncSession,
    text: str,
    course: Course | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Send `text` to the owner. If `course` has a banner image, send it as a
    photo with `text` as the caption instead of a separate message.
    Falls back to plain text if the image is missing/corrupted/too long.
    """
    chat_id = settings.owner_telegram_id

    if course is not None and course.image_path:
        try:
            if course.banner_file_id:
                photo = course.banner_file_id
            else:
                image_path = settings.base_dir / course.image_path
                if not image_path.is_file():
                    raise FileNotFoundError(image_path)
                photo = FSInputFile(image_path)

            if len(text) > 1024:
                # Telegram caption limit; send image then text separately.
                message = await bot.send_photo(chat_id, photo=photo)
                await bot.send_message(chat_id, text, reply_markup=reply_markup)
            else:
                message = await bot.send_photo(
                    chat_id, photo=photo, caption=text, reply_markup=reply_markup
                )

            if not course.banner_file_id and message.photo:
                course.banner_file_id = message.photo[-1].file_id
                session.add(course)
                await session.commit()
            return
        except Exception:
            logger.exception("Failed to send banner for course_id=%s, falling back to text", course.id)

    await bot.send_message(chat_id, text, reply_markup=reply_markup)
