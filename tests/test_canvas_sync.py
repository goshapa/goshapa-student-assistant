"""Offline Canvas failure regressions against an in-memory database."""
import os
os.environ.setdefault("BOT_TOKEN", "123:test")
os.environ.setdefault("OWNER_TELEGRAM_ID", "1")

import unittest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import Base, Assignment, Course
from services import canvas_sync
from services.canvas_api import CanvasAPIError


class CanvasSyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.maker = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.maker() as session:
            session.add(Course(course_code="COSC-1520-3T", title="Computer Programming Concepts"))
            session.add(Assignment(canvas_assignment_id=10, canvas_course_id=1,
                name="Existing", is_active=True, is_submitted=True))
            await session.commit()
        self.api = AsyncMock()
        self.api.get_active_courses.return_value = [dict(id=1, name="Programming", course_code="COSC 1520 3T FA 2026")]

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def sync(self):
        with patch.object(canvas_sync, "async_session_maker", self.maker), \
             patch.object(canvas_sync, "CanvasAPI", return_value=self.api), \
             patch.object(canvas_sync, "send_with_optional_banner", new_callable=AsyncMock):
            return await canvas_sync.sync_canvas(AsyncMock())

    async def test_failed_course_preserves_assignments(self):
        self.api.get_assignments.side_effect = CanvasAPIError("unavailable")
        result = await self.sync()
        self.assertFalse(result.ok)
        async with self.maker() as session:
            self.assertTrue((await session.get(Assignment, 1)).is_active)

    async def test_failed_submission_preserves_submitted(self):
        self.api.get_assignments.return_value = [dict(id=10, name="Existing")]
        self.api.get_submission.side_effect = CanvasAPIError("unavailable")
        self.assertFalse((await self.sync()).ok)
        async with self.maker() as session:
            self.assertTrue((await session.get(Assignment, 1)).is_submitted)

    async def test_webster_match_and_successful_removal(self):
        self.api.get_assignments.return_value = []
        self.assertTrue((await self.sync()).ok)
        async with self.maker() as session:
            self.assertEqual((await session.get(Course, 1)).canvas_course_id, 1)
            self.assertFalse((await session.get(Assignment, 1)).is_active)
