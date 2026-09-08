"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int | None = None, required: bool = False) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return default  # type: ignore[return-value]
    return int(raw)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_telegram_id: int

    canvas_base_url: str | None
    canvas_access_token: str | None

    timezone_name: str
    timezone: ZoneInfo = field(init=False)

    morning_briefing_time: str
    evening_briefing_time: str

    canvas_sync_interval_minutes: int

    base_dir: Path = BASE_DIR
    db_path: Path = field(init=False)
    assets_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    log_file: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "timezone", ZoneInfo(self.timezone_name))
        data_dir = Path(os.environ["DATA_DIR"]).expanduser().resolve() if os.getenv("DATA_DIR") else None
        object.__setattr__(self, "db_path", (data_dir or self.base_dir / "database") / "student.db")
        object.__setattr__(self, "assets_dir", self.base_dir / "assets" / "courses")
        object.__setattr__(self, "logs_dir", (data_dir or self.base_dir) / "logs")
        object.__setattr__(self, "log_file", self.logs_dir / "bot.log")


def load_settings() -> Settings:
    canvas_base_url = os.getenv("CANVAS_BASE_URL") or None
    canvas_access_token = os.getenv("CANVAS_ACCESS_TOKEN") or None

    if canvas_base_url:
        canvas_base_url = canvas_base_url.rstrip("/")

    return Settings(
        bot_token=_get_required("BOT_TOKEN"),
        owner_telegram_id=_get_int("OWNER_TELEGRAM_ID", required=True),
        canvas_base_url=canvas_base_url,
        canvas_access_token=canvas_access_token,
        timezone_name=os.getenv("TIMEZONE", "Asia/Tashkent"),
        morning_briefing_time=os.getenv("MORNING_BRIEFING_TIME", "09:00"),
        evening_briefing_time=os.getenv("EVENING_BRIEFING_TIME", "21:00"),
        canvas_sync_interval_minutes=_get_int("CANVAS_SYNC_INTERVAL_MINUTES", default=15),
    )


settings = load_settings()
