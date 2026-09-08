"""Entry point: wires up the dispatcher, middleware, scheduler and starts polling."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import init_db
from handlers import admin, assignments, canvas, deadlines, schedule, settings as settings_handlers, start
from middlewares import OwnerOnlyMiddleware
from scheduler import create_scheduler
from services.canvas_sync import sync_canvas
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("Starting Goshapa Student Assistant...")

    await init_db()
    logger.info("Database ready")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    owner_only = OwnerOnlyMiddleware()
    dp.message.middleware(owner_only)
    dp.callback_query.middleware(owner_only)

    dp.include_router(start.router)
    dp.include_router(schedule.router)
    dp.include_router(assignments.router)
    dp.include_router(deadlines.router)
    dp.include_router(canvas.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(admin.router)

    scheduler = create_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started")

    try:
        if settings.canvas_base_url and settings.canvas_access_token:
            logger.info("Running initial Canvas sync...")
            result = await sync_canvas(bot)
            if result.ok:
                logger.info(
                    "Initial Canvas sync done: %s courses, %s active assignments, %s new",
                    result.courses, result.active_assignments, result.new_assignments,
                )
            else:
                logger.warning("Initial Canvas sync failed: %s", result.error)
        else:
            logger.info("Canvas is not configured; skipping initial sync")

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot is polling...")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted, shutting down")
