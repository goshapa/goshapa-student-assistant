"""Inline keyboards for the settings section."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Course, Settings as SettingsModel
from keyboards.callback_data import ManageCB, ManageCourseCB, SettingsMenuCB, SettingsToggleCB, WeekdayCB

WEEKDAY_LABELS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Lesson reminders", callback_data=SettingsMenuCB(section="lesson").pack())],
            [InlineKeyboardButton(text="📚 Assignment reminders", callback_data=SettingsMenuCB(section="assignment").pack())],
            [InlineKeyboardButton(text="☀️ Morning briefing", callback_data=SettingsMenuCB(section="morning").pack())],
            [InlineKeyboardButton(text="🌙 Evening briefing", callback_data=SettingsMenuCB(section="evening").pack())],
            [InlineKeyboardButton(text="🎓 Canvas", callback_data=SettingsMenuCB(section="canvas").pack())],
            [InlineKeyboardButton(text="📚 Manage Schedule", callback_data=SettingsMenuCB(section="manage").pack())],
        ]
    )


def _toggle_label(label: str, enabled: bool) -> str:
    return f"{'✅' if enabled else '⬜️'} {label}"


def lesson_reminders_keyboard(s: SettingsModel) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=_toggle_label("1 hour before", s.lesson_reminder_1h),
                callback_data=SettingsToggleCB(field="lesson_reminder_1h").pack(),
            )],
            [InlineKeyboardButton(
                text=_toggle_label("15 minutes before", s.lesson_reminder_15m),
                callback_data=SettingsToggleCB(field="lesson_reminder_15m").pack(),
            )],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=SettingsMenuCB(section="root").pack())],
        ]
    )


def assignment_reminders_keyboard(s: SettingsModel) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=_toggle_label("3 days", s.assignment_reminder_3d),
                callback_data=SettingsToggleCB(field="assignment_reminder_3d").pack(),
            )],
            [InlineKeyboardButton(
                text=_toggle_label("24 hours", s.assignment_reminder_24h),
                callback_data=SettingsToggleCB(field="assignment_reminder_24h").pack(),
            )],
            [InlineKeyboardButton(
                text=_toggle_label("6 hours", s.assignment_reminder_6h),
                callback_data=SettingsToggleCB(field="assignment_reminder_6h").pack(),
            )],
            [InlineKeyboardButton(
                text=_toggle_label("1 hour", s.assignment_reminder_1h),
                callback_data=SettingsToggleCB(field="assignment_reminder_1h").pack(),
            )],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=SettingsMenuCB(section="root").pack())],
        ]
    )


def briefing_keyboard(section: str, enabled: bool) -> InlineKeyboardMarkup:
    field = "morning_briefing_enabled" if section == "morning" else "evening_briefing_enabled"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=_toggle_label("Enabled", enabled),
                callback_data=SettingsToggleCB(field=field).pack(),
            )],
            [InlineKeyboardButton(
                text="🕘 Change time",
                callback_data=SettingsMenuCB(section=f"{section}_time").pack(),
            )],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=SettingsMenuCB(section="root").pack())],
        ]
    )


def manage_schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить пару", callback_data=ManageCB(action="add").pack())],
            [InlineKeyboardButton(text="✏️ Изменить пару", callback_data=ManageCB(action="edit").pack())],
            [InlineKeyboardButton(text="❌ Отменить пару", callback_data=ManageCB(action="cancel").pack())],
            [InlineKeyboardButton(text="🔄 Перенести пару", callback_data=ManageCB(action="reschedule").pack())],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=SettingsMenuCB(section="root").pack())],
        ]
    )


def cancel_fsm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✖️ Cancel", callback_data=ManageCB(action="fsm_cancel").pack())]]
    )


def weekday_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=WeekdayCB(weekday=i).pack())]
            for i, label in enumerate(WEEKDAY_LABELS)
        ]
    )


def manage_course_list_keyboard(courses: list[Course], action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=c.title,
                    callback_data=ManageCourseCB(action=action, course_id=c.id).pack(),
                )
            ]
            for c in courses
        ]
    )


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    from keyboards.callback_data import ConfirmCB

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=ConfirmCB(action=action, value="yes").pack()),
                InlineKeyboardButton(text="❌ Нет", callback_data=ConfirmCB(action=action, value="no").pack()),
            ]
        ]
    )
