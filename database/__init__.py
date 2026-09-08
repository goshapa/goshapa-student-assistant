"""Database engine/session setup and initialization.

Exposed here (instead of a separate top-level database.py) to avoid a
module/package name collision with this `database/` package.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.models import Base, Settings as SettingsModel
from database.seed import seed_initial_schedule
from utils.logger import get_logger

logger = get_logger(__name__)

settings.db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(f"sqlite+aiosqlite:///{settings.db_path}", echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        columns = await conn.execute(text("PRAGMA table_info(lesson_exceptions)"))
        if "new_date" not in {row[1] for row in columns}:
            await conn.execute(text("ALTER TABLE lesson_exceptions ADD COLUMN new_date DATE"))
    logger.info("Database schema ensured at %s", settings.db_path)

    async with async_session_maker() as session:
        await seed_initial_schedule(session)

        existing = await session.get(SettingsModel, 1)
        if existing is None:
            session.add(
                SettingsModel(
                    id=1,
                    morning_briefing_time=settings.morning_briefing_time,
                    evening_briefing_time=settings.evening_briefing_time,
                )
            )
            await session.commit()
            logger.info("Default settings row created")
