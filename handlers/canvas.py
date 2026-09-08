"""Manual Canvas sync trigger."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from keyboards.main import BTN_SYNC
from services.canvas_sync import sync_canvas
from utils.datetime_utils import now_tz
from utils.formatting import format_sync_result
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="canvas")


@router.message(Command("sync"))
@router.message(F.text == BTN_SYNC)
async def sync_canvas_handler(message: Message) -> None:
    status_message = await message.answer("🔄 Syncing Canvas...")

    result = await sync_canvas(message.bot)

    if not result.ok:
        if result.error == "not_configured":
            await status_message.edit_text(
                "⚠️ Canvas is not configured.\n\n"
                "Set CANVAS_BASE_URL and CANVAS_ACCESS_TOKEN in .env to enable sync."
            )
        else:
            await status_message.edit_text(
                "⚠️ Canvas synchronization failed.\n\n"
                "Your schedule and existing assignments are still available.\n\n"
                "Next automatic sync will try again."
            )
        return

    text = format_sync_result(
        result.courses, result.active_assignments, result.new_assignments, result.submitted, now_tz()
    )
    await status_message.edit_text(text)
