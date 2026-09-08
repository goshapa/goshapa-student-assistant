"""Timezone-aware date/time helpers. Everything user-facing is Asia/Tashkent."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from config import settings

TASHKENT_TZ: ZoneInfo = settings.timezone

WEEKDAY_NAMES_EN = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

WEEKDAY_NAMES_EN_UPPER = [w.upper() for w in WEEKDAY_NAMES_EN]

MONTH_NAMES_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def now_tz() -> datetime:
    return datetime.now(TASHKENT_TZ)


def today_tz() -> date:
    return now_tz().date()


def to_tz(dt: datetime) -> datetime:
    """Convert an aware (or naive-UTC) datetime to Asia/Tashkent."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TASHKENT_TZ)


def to_utc(dt: datetime) -> datetime:
    """SQLite's naive timestamps represent UTC, never local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def same_instant(left: datetime | None, right: datetime | None) -> bool:
    """Compare API and database timestamps, including missing deadlines."""
    if left is None or right is None:
        return left is right
    return to_utc(left) == to_utc(right)


def parse_canvas_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 UTC string from Canvas (e.g. 2026-09-15T18:59:00Z)."""
    if not value:
        return None
    v = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return to_utc(dt)


def parse_time_str(value: str) -> time:
    """Parse 'HH:MM' into a time object."""
    hour, minute = value.strip().split(":")
    return time(int(hour), int(minute))


def format_time(dt: datetime | time) -> str:
    if isinstance(dt, datetime):
        dt = to_tz(dt).time()
    return dt.strftime("%H:%M")


def format_date_human(d: date) -> str:
    """e.g. 'September 15'."""
    return f"{MONTH_NAMES_EN[d.month - 1]} {d.day}"


def format_weekday_date(d: date) -> str:
    """e.g. 'Wednesday, September 9'."""
    return f"{WEEKDAY_NAMES_EN[d.weekday()]}, {format_date_human(d)}"


def format_date_full(d: date) -> str:
    """e.g. '24.08.2026'."""
    return d.strftime("%d.%m.%Y")


def format_duration_until(target: datetime) -> str:
    """Human 'X ч. Y мин.' countdown from now until target (Tashkent-aware)."""
    delta = to_utc(target) - to_utc(now_tz())
    if delta.total_seconds() <= 0:
        return "0 мин."
    total_minutes = int(delta.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} ч. {minutes} мин."
    if hours:
        return f"{hours} ч."
    return f"{minutes} мин."


def format_time_left_short(target: datetime) -> str:
    """e.g. '7 days left' / '8 hours left', used for assignment deadlines."""
    delta = to_utc(target) - to_utc(now_tz())
    seconds = delta.total_seconds()
    if seconds <= 0:
        return "overdue"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    if days >= 1:
        return f"{days} day{'s' if days != 1 else ''} left"
    if hours >= 1:
        return f"{hours} hour{'s' if hours != 1 else ''} left"
    minutes = int((seconds % 3600) // 60)
    return f"{minutes} min left"


def combine_date_time(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=TASHKENT_TZ)


def deadline_status_emoji(due_at: datetime) -> str:
    """🔴 <24h, 🟠 <3d, 🟡 <7d, 🟢 >7d."""
    delta = to_utc(due_at) - to_utc(now_tz())
    hours = delta.total_seconds() / 3600
    if hours < 24:
        return "🔴"
    if hours < 24 * 3:
        return "🟠"
    if hours < 24 * 7:
        return "🟡"
    return "🟢"


def relative_day_label(d: date) -> str | None:
    """Return 'TODAY' / 'TOMORROW' / None if not today/tomorrow."""
    today = today_tz()
    if d == today:
        return "TODAY"
    if d == today + timedelta(days=1):
        return "TOMORROW"
    return None
