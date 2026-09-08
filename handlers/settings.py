"""Settings menu: reminder toggles, briefing times, Canvas status."""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import settings as app_settings
from database import get_session
from database.models import Settings as SettingsModel
from keyboards.main import BTN_SETTINGS
from keyboards.settings import (
    assignment_reminders_keyboard,
    briefing_keyboard,
    lesson_reminders_keyboard,
    manage_schedule_keyboard,
    settings_menu_keyboard,
)
from keyboards.callback_data import NavCB, SettingsMenuCB, SettingsToggleCB
from utils.datetime_utils import to_tz
from utils.formatting import format_time
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="settings")

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class SettingsStates(StatesGroup):
    waiting_morning_time = State()
    waiting_evening_time = State()


async def _get_settings(session) -> SettingsModel:
    row = await session.get(SettingsModel, 1)
    assert row is not None
    return row


@router.message(Command("settings"))
@router.message(F.text == BTN_SETTINGS)
async def show_settings(message: Message) -> None:
    await message.answer("⚙️ SETTINGS", reply_markup=settings_menu_keyboard())


@router.callback_query(SettingsMenuCB.filter())
async def on_settings_menu(callback: CallbackQuery, callback_data: SettingsMenuCB, state: FSMContext) -> None:
    section = callback_data.section

    if section == "root":
        await callback.message.edit_text("⚙️ SETTINGS", reply_markup=settings_menu_keyboard())
        await callback.answer()
        return

    async with get_session() as session:
        s = await _get_settings(session)

        if section == "lesson":
            await callback.message.edit_text("🔔 Lesson reminders", reply_markup=lesson_reminders_keyboard(s))
        elif section == "assignment":
            await callback.message.edit_text("📚 Assignment reminders", reply_markup=assignment_reminders_keyboard(s))
        elif section == "morning":
            await callback.message.edit_text(
                f"☀️ Morning briefing\n\nTime: {s.morning_briefing_time}",
                reply_markup=briefing_keyboard("morning", s.morning_briefing_enabled),
            )
        elif section == "evening":
            await callback.message.edit_text(
                f"🌙 Evening briefing\n\nTime: {s.evening_briefing_time}",
                reply_markup=briefing_keyboard("evening", s.evening_briefing_enabled),
            )
        elif section == "canvas":
            configured = bool(app_settings.canvas_base_url and app_settings.canvas_access_token)
            last_sync = format_time(to_tz(s.last_canvas_sync_at)) if s.last_canvas_sync_at else "never"
            text = (
                "🎓 Canvas\n\n"
                f"Configured: {'✅ yes' if configured else '❌ no'}\n"
                f"Base URL: {app_settings.canvas_base_url or '—'}\n"
                f"Last sync: {last_sync}"
            )
            from keyboards.schedule import back_keyboard

            await callback.message.edit_text(text, reply_markup=back_keyboard("settings_root"))
        elif section == "manage":
            await callback.message.edit_text("📚 Manage Schedule", reply_markup=manage_schedule_keyboard())
        elif section == "morning_time":
            await state.set_state(SettingsStates.waiting_morning_time)
            await callback.message.answer("Введите новое время утренней сводки в формате ЧЧ:ММ (например 09:00):")
        elif section == "evening_time":
            await state.set_state(SettingsStates.waiting_evening_time)
            await callback.message.answer("Введите новое время вечерней сводки в формате ЧЧ:ММ (например 21:00):")

    await callback.answer()


@router.callback_query(NavCB.filter(F.target == "settings_root"))
async def on_back_to_settings_root(callback: CallbackQuery) -> None:
    await callback.message.edit_text("⚙️ SETTINGS", reply_markup=settings_menu_keyboard())
    await callback.answer()


@router.callback_query(SettingsToggleCB.filter())
async def on_settings_toggle(callback: CallbackQuery, callback_data: SettingsToggleCB) -> None:
    field = callback_data.field

    async with get_session() as session:
        s = await _get_settings(session)
        current = getattr(s, field)
        setattr(s, field, not current)
        await session.commit()

        if field.startswith("lesson_reminder"):
            await callback.message.edit_text("🔔 Lesson reminders", reply_markup=lesson_reminders_keyboard(s))
        elif field.startswith("assignment_reminder"):
            await callback.message.edit_text("📚 Assignment reminders", reply_markup=assignment_reminders_keyboard(s))
        elif field == "morning_briefing_enabled":
            await callback.message.edit_text(
                f"☀️ Morning briefing\n\nTime: {s.morning_briefing_time}",
                reply_markup=briefing_keyboard("morning", s.morning_briefing_enabled),
            )
        elif field == "evening_briefing_enabled":
            await callback.message.edit_text(
                f"🌙 Evening briefing\n\nTime: {s.evening_briefing_time}",
                reply_markup=briefing_keyboard("evening", s.evening_briefing_enabled),
            )

    await callback.answer()


@router.message(SettingsStates.waiting_morning_time)
async def set_morning_time(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not TIME_RE.match(text):
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ, например 09:00.")
        return

    async with get_session() as session:
        s = await _get_settings(session)
        s.morning_briefing_time = text
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Morning briefing time set to {text}", reply_markup=settings_menu_keyboard())


@router.message(SettingsStates.waiting_evening_time)
async def set_evening_time(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not TIME_RE.match(text):
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ, например 21:00.")
        return

    async with get_session() as session:
        s = await _get_settings(session)
        s.evening_briefing_time = text
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Evening briefing time set to {text}", reply_markup=settings_menu_keyboard())
