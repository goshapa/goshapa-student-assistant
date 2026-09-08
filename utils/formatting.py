"""Builds all user-facing message text."""
from __future__ import annotations

from datetime import date

from database.models import Assignment, Course
from services.schedule_service import LessonOccurrence
from utils.datetime_utils import (
    deadline_status_emoji,
    format_date_human,
    format_duration_until,
    format_time,
    format_time_left_short,
    format_weekday_date,
    now_tz,
    to_tz,
)

COURSE_EMOJI = {
    "COSC-1570-3T": "🧮",
    "EDEX-1500-5T": "🎓",
    "COSC-1520-3T": "💻",
    "GLBC-1200-5K": "🌎",
    "SPCM-1040-9T": "🎤",
}


def course_emoji(course_code: str) -> str:
    return COURSE_EMOJI.get(course_code, "📘")


def short_building(building: str) -> str:
    """'Tashkent North Hall' -> 'North Hall'."""
    return building.replace("Tashkent ", "")


def format_lesson_block(occ: LessonOccurrence, *, with_countdown: bool = False) -> str:
    emoji = course_emoji(occ.course.course_code)
    lines = [
        f"{emoji} {occ.course.title}",
        f"🕖 {format_time(occ.start_time)}–{format_time(occ.end_time)}",
        f"📍 {short_building(occ.building)} — Room {occ.room}",
    ]
    if with_countdown:
        lines.append("")
        lines.append(f"До начала: {format_duration_until(occ.start_dt)}")
    return "\n".join(lines)


def format_today_message(occurrences: list[LessonOccurrence], today: date) -> str:
    header = f"📅 {format_weekday_date(today)}"
    if not occurrences:
        return f"{header}\n\n😎 Сегодня занятий нет."

    parts = [header, "", "Сегодня у тебя:", ""]
    for occ in occurrences:
        parts.append(format_lesson_block(occ, with_countdown=occ is occurrences[0]))
        parts.append("")
    return "\n".join(parts).rstrip()


def format_tomorrow_message(occurrences: list[LessonOccurrence]) -> str:
    header = "📅 Tomorrow"
    if not occurrences:
        return f"{header}\n\n😎 Завтра занятий нет."

    parts = [header, ""]
    for occ in occurrences:
        parts.append(format_lesson_block(occ))
        parts.append("")
    return "\n".join(parts).rstrip()


def format_week_message(week: dict[date, list[LessonOccurrence]]) -> str:
    if not week:
        return "📚 WEEK SCHEDULE\n\n😎 На этой неделе занятий нет."

    parts = ["📚 WEEK SCHEDULE", ""]
    for day, occs in sorted(week.items()):
        parts.append(day.strftime("%A").upper())
        for occ in occs:
            emoji = course_emoji(occ.course.course_code)
            parts.append(f"{format_time(occ.start_time)} — {occ.course.title}")
            parts.append(f"📍 {short_building(occ.building)} {occ.room}")
        parts.append("")
    return "\n".join(parts).rstrip()


def format_course_card(course: Course, occ: LessonOccurrence | None) -> str:
    parts = [
        f"📚 {course.title}",
        f"🔖 {course.course_code}",
        "",
    ]
    if occ is not None:
        parts.append(f"📅 {occ.occurrence_date.strftime('%A')}")
        parts.append(f"🕟 {format_time(occ.start_time)}–{format_time(occ.end_time)}")
        parts.append(f"📍 {short_building(occ.building)} — Room {occ.room}")
        parts.append("")
    return "\n".join(parts).rstrip()


def format_lesson_reminder(occ: LessonOccurrence, minutes_before: int) -> str:
    emoji = course_emoji(occ.course.course_code)
    if minutes_before == 60:
        return (
            "⏰ Через 1 час пара!\n\n"
            f"{emoji} {occ.course.title}\n\n"
            f"🕖 {format_time(occ.start_time)}–{format_time(occ.end_time)}\n"
            f"📍 {short_building(occ.building)} — Room {occ.room}"
        )
    return (
        "🚨 Через 15 минут начинается пара!\n\n"
        f"{emoji} {occ.course.title}\n"
        f"📍 {short_building(occ.building)} — {occ.room}"
    )


def assignment_status_line(a: Assignment) -> str:
    if a.is_missing:
        return "🚨 MISSING"
    if a.is_late:
        return "⚠️ LATE"
    if a.is_submitted:
        return "✅ SUBMITTED"
    return "❌ NOT SUBMITTED"


def format_new_assignment(a: Assignment, course: Course | None) -> str:
    parts = ["🆕 NEW ASSIGNMENT", ""]
    if course is not None:
        emoji = course_emoji(course.course_code)
        parts.append(f"{emoji} {course.title}")
        parts.append("")
    parts.append(f"📄 {a.name}")
    parts.append("")

    if a.due_at is None:
        parts.append("📅 Deadline:\nNot specified")
        parts.append("")
        parts.append("⚠️ Professor did not set a due date.")
    else:
        due_local = to_tz(a.due_at)
        parts.append("📅 Deadline:")
        parts.append(f"{format_date_human(due_local.date())} — {format_time(due_local)}")
        parts.append("")
        parts.append(f"⏳ Осталось: {format_time_left_short(a.due_at)}")

    if a.points_possible:
        parts.append("")
        parts.append(f"🎯 Points: {int(a.points_possible)}")

    parts.append("")
    parts.append("🔗 Open Canvas")
    return "\n".join(parts)


def format_active_assignments(items: list[tuple[Assignment, Course | None]]) -> str:
    if not items:
        return "📚 ACTIVE ASSIGNMENTS — 0\n\nНет активных заданий 😎"

    parts = [f"📚 ACTIVE ASSIGNMENTS — {len(items)}", ""]
    for a, course in items:
        status_emoji = deadline_status_emoji(a.due_at) if a.due_at else "🟢"
        course_title = course.title if course else "Unknown course"
        parts.append(f"{status_emoji} {course_title}")
        parts.append("")
        parts.append(a.name)
        if a.due_at:
            due_local = to_tz(a.due_at)
            day_label = _relative_or_date(due_local.date())
            parts.append(f"📅 {day_label} — {format_time(due_local)}")
            parts.append(f"⏳ {format_time_left_short(a.due_at)}")
        else:
            parts.append("📅 No due date")
        parts.append("")
    return "\n".join(parts).rstrip()


def _relative_or_date(d: date) -> str:
    from utils.datetime_utils import relative_day_label

    label = relative_day_label(d)
    if label:
        return label.capitalize()
    return format_date_human(d)


def format_deadlines(items: list[Assignment]) -> str:
    if not items:
        return "⏰ UPCOMING DEADLINES\n\nНет активных дедлайнов 😎"

    parts = ["⏰ UPCOMING DEADLINES", ""]
    grouped: dict[str, list[Assignment]] = {}
    for a in items:
        due_local = to_tz(a.due_at)
        label = _relative_or_date(due_local.date())
        if label not in ("Today", "Tomorrow"):
            label = f"IN {(due_local.date() - now_tz().date()).days} DAYS"
        else:
            label = label.upper()
        grouped.setdefault(label, []).append(a)

    for label, assignments in grouped.items():
        parts.append(label)
        for a in assignments:
            due_local = to_tz(a.due_at)
            parts.append(f"{deadline_status_emoji(a.due_at)} {a.name}")
            parts.append(format_time(due_local))
        parts.append("")
    return "\n".join(parts).rstrip()


def format_submitted(items: list[tuple[Assignment, Course | None]]) -> str:
    if not items:
        return "✅ SUBMITTED ASSIGNMENTS\n\nПока ничего не сдано."

    parts = ["✅ SUBMITTED ASSIGNMENTS", ""]
    grouped: dict[str, list[Assignment]] = {}
    for a, course in items:
        title = course.title if course else "Unknown course"
        grouped.setdefault(title, []).append(a)

    for title, assignments in grouped.items():
        parts.append(title)
        for a in assignments:
            parts.append(f"✅ {a.name}")
        parts.append("")
    return "\n".join(parts).rstrip()


def format_morning_briefing(
    occurrences: list[LessonOccurrence],
    active_count: int,
    due_today_count: int,
    nearest_deadline: Assignment | None,
) -> str:
    parts = ["☀️ GOOD MORNING, GOSHA", ""]
    if not occurrences:
        parts.append("Сегодня пар нет 😎")
        parts.append("")
        parts.append(f"📚 Active assignments: {active_count}")
        if nearest_deadline and nearest_deadline.due_at:
            days = (to_tz(nearest_deadline.due_at).date() - now_tz().date()).days
            if days > 0:
                parts.append(f"⏰ Ближайший дедлайн через {days} {_ru_days(days)}")
        return "\n".join(parts)

    parts.append("Сегодня:")
    parts.append("")
    for occ in occurrences:
        parts.append(format_lesson_block(occ))
        parts.append("")
    parts.append(f"📚 Active assignments: {active_count}")
    if due_today_count:
        parts.append(f"🚨 Due today: {due_today_count}")
    if nearest_deadline:
        parts.append("")
        parts.append("Ближайший deadline:")
        if nearest_deadline.due_at:
            parts.append(f"{nearest_deadline.name} — {format_time(to_tz(nearest_deadline.due_at))}")
        else:
            parts.append(nearest_deadline.name)
    return "\n".join(parts).rstrip()


def _ru_days(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    if 2 <= days % 10 <= 4 and not (12 <= days % 100 <= 14):
        return "дня"
    return "дней"


def format_evening_briefing(
    occurrences: list[LessonOccurrence], active_count: int
) -> str:
    parts = ["🌙 TOMORROW", ""]
    if not occurrences:
        parts.append("Завтра занятий нет 😎")
    else:
        parts.append("Завтра у тебя:")
        parts.append("")
        for occ in occurrences:
            parts.append(format_lesson_block(occ))
            parts.append("")
        parts.append(f"📚 {active_count} active assignments")

        first = occurrences[0]
        if first.start_time.hour < 9:
            parts.append("")
            parts.append(f"⚠️ Первая пара завтра в {format_time(first.start_time)}.")
            parts.append("Не забудь поставить будильник.")
    return "\n".join(parts).rstrip()


def format_deadline_reminder(a: Assignment, course: Course | None, kind: str) -> str:
    course_title = course.title if course else "Unknown course"
    emoji = course_emoji(course.course_code) if course else "📘"

    if kind == "3_days":
        due_local = to_tz(a.due_at)
        return (
            "📚 Assignment reminder\n\n"
            f"{emoji} {course_title}\n\n"
            f"{a.name}\n\n"
            f"📅 Deadline через 3 дня\n"
            f"{format_date_human(due_local.date())} — {format_time(due_local)}\n\n"
            "❌ Not submitted"
        )
    if kind == "24_hours":
        return (
            "⚠️ DEADLINE TOMORROW\n\n"
            f"📄 {a.name}\n\n"
            f"{emoji} {course_title}\n\n"
            "⏳ Осталось 24 часа\n"
            "❌ Not submitted"
        )
    if kind == "6_hours":
        return (
            "🚨 DEADLINE IN 6 HOURS\n\n"
            f"{a.name}\n\n"
            "❌ Ты ещё не сдал assignment."
        )
    if kind == "1_hour":
        due_local = to_tz(a.due_at)
        return (
            "🚨🚨 DEADLINE IN ONE HOUR\n\n"
            f"📄 {a.name}\n\n"
            f"⏰ {format_time(due_local)}\n\n"
            "❌ NOT SUBMITTED\n\n"
            "Gosha, пора заканчивать 💀"
        )
    raise ValueError(f"Unknown reminder kind: {kind}")


def format_missed_deadline(a: Assignment, course: Course | None) -> str:
    course_title = course.title if course else "Unknown course"
    emoji = course_emoji(course.course_code) if course else "📘"
    due_local = to_tz(a.due_at) if a.due_at else None
    return (
        "💀 MISSED DEADLINE\n\n"
        f"{a.name}\n\n"
        f"{emoji} {course_title}\n\n"
        f"Deadline был:\n{format_time(due_local) if due_local else '—'}\n\n"
        "Status:\n❌ Missing"
    )


def format_submitted_notification(a: Assignment) -> str:
    return (
        "✅ Assignment submitted\n\n"
        f"{a.name}\n\n"
        "Напоминания по этому заданию отключены 😎"
    )


def format_deadline_changed(a: Assignment, old_due, new_due) -> str:
    parts = ["⚠️ DEADLINE CHANGED", "", a.name, ""]
    if old_due:
        old_local = to_tz(old_due)
        parts.append(f"Old:\n{format_date_human(old_local.date())} — {format_time(old_local)}")
    else:
        parts.append("Old:\nNot specified")
    if new_due:
        new_local = to_tz(new_due)
        parts.append("")
        parts.append(f"New:\n{format_date_human(new_local.date())} — {format_time(new_local)}")
    else:
        parts.append("\nNew:\nNot specified")
    return "\n".join(parts)


def format_sync_result(
    courses: int, active_assignments: int, new_assignments: int, submitted: int, last_sync
) -> str:
    return (
        "✅ Canvas synchronized\n\n"
        f"Courses: {courses}\n"
        f"Active assignments: {active_assignments}\n"
        f"New assignments: {new_assignments}\n"
        f"Submitted: {submitted}\n\n"
        f"Last sync:\n{format_time(to_tz(last_sync))}"
    )
