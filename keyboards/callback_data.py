"""Structured callback_data factories shared across keyboards/handlers."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class CourseCB(CallbackData, prefix="course"):
    action: str  # "view" | "assignments" | "deadlines" | "next"
    course_id: int


class AssignmentCB(CallbackData, prefix="asg"):
    assignment_id: int
    page: int = 0
    course_id: int = 0
    list_page: int = 0


class AssignmentListCB(CallbackData, prefix="asgl"):
    page: int = 0
    course_id: int = 0


class SettingsToggleCB(CallbackData, prefix="stgtog"):
    field: str


class SettingsMenuCB(CallbackData, prefix="stgmenu"):
    section: str


class ManageCB(CallbackData, prefix="mng"):
    action: str  # "add" | "edit" | "cancel" | "reschedule" | "back"


class ManageCourseCB(CallbackData, prefix="mngcourse"):
    action: str  # "edit" | "cancel" | "reschedule"
    course_id: int


class ConfirmCB(CallbackData, prefix="confirm"):
    action: str  # "cancel_lesson" | "edit_lesson" | "reschedule_lesson"
    value: str  # "yes" | "no"


class NavCB(CallbackData, prefix="nav"):
    target: str


class WeekdayCB(CallbackData, prefix="wd"):
    weekday: int
