"""Offline regressions; run with python -m unittest discover -s tests."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


# Load only the utility under test: tests need neither .env nor API credentials.
spec = importlib.util.spec_from_file_location(
    "datetime_under_test", Path(__file__).resolve().parents[1] / "utils/datetime_utils.py"
)
dates = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"config": SimpleNamespace(
    settings=SimpleNamespace(timezone=ZoneInfo("Asia/Tashkent"))
)}):
    spec.loader.exec_module(dates)


class DatetimeTests(unittest.TestCase):
    def test_sqlite_roundtrip_matches_canvas(self):
        api_due = dates.parse_canvas_datetime("2026-09-15T18:59:00Z")
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE assignments (due_at TEXT)")
            db.execute("INSERT INTO assignments VALUES (?)", (
                api_due.replace(tzinfo=None).isoformat(),
            ))
            loaded = datetime.fromisoformat(db.execute(
                "SELECT due_at FROM assignments"
            ).fetchone()[0])
        self.assertTrue(dates.same_instant(loaded, api_due))
        self.assertEqual(dates.to_tz(loaded).strftime("%H:%M"), "23:59")

    def test_offset_is_normalized_before_storage(self):
        actual = dates.parse_canvas_datetime("2026-09-15T23:59:00+05:00")
        self.assertEqual(actual.hour, 18)
        self.assertEqual(actual.utcoffset(), timedelta(0))

    def test_added_removed_and_changed_deadlines(self):
        due = datetime(2026, 9, 15, 18, 59)
        self.assertTrue(dates.same_instant(None, None))
        self.assertFalse(dates.same_instant(None, due))
        self.assertFalse(dates.same_instant(due, None))
        self.assertFalse(dates.same_instant(due, due + timedelta(hours=1)))

    def test_countdowns_accept_database_dates(self):
        now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
        with patch.object(dates, "now_tz", return_value=now):
            self.assertEqual(dates.format_time_left_short(
                datetime(2026, 9, 8, 20)), "8 hours left")
            self.assertEqual(dates.format_duration_until(
                datetime(2026, 9, 8, 13, 30)), "1 ч. 30 мин.")
            self.assertEqual(dates.format_time_left_short(
                datetime(2026, 9, 8, 11)), "overdue")

    def test_deadline_color_boundaries(self):
        now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
        with patch.object(dates, "now_tz", return_value=now):
            for hours, expected in [(23, "🔴"), (24, "🟠"), (72, "🟡"), (168, "🟢")]:
                with self.subTest(hours=hours):
                    due = (now + timedelta(hours=hours)).replace(tzinfo=None)
                    self.assertEqual(dates.deadline_status_emoji(due), expected)


if __name__ == "__main__":
    unittest.main()
