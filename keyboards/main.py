"""Main reply keyboard (persistent bottom menu)."""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_TODAY = "📅 Сегодня"
BTN_TOMORROW = "➡️ Завтра"
BTN_WEEK = "🗓 Неделя"
BTN_ASSIGNMENTS = "📚 Assignments"
BTN_DEADLINES = "⏰ Deadlines"
BTN_SUBMITTED = "✅ Submitted"
BTN_SETTINGS = "⚙️ Настройки"
BTN_SYNC = "🔄 Sync Canvas"
BTN_MY_COURSES = "🎓 Мои предметы"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_TOMORROW)],
            [KeyboardButton(text=BTN_WEEK), KeyboardButton(text=BTN_ASSIGNMENTS)],
            [KeyboardButton(text=BTN_DEADLINES), KeyboardButton(text=BTN_SUBMITTED)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_SYNC)],
            [KeyboardButton(text=BTN_MY_COURSES)],
        ],
        resize_keyboard=True,
    )
