from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_port: int = 8000
    backend_admin_token: str = "change-me"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'bot.db'}"

    bridge_port: int = 3000
    bridge_token: str = "change-me"
    bridge_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-v4-flash:nitro"
    openrouter_fallback_model: str = "anthropic/claude-haiku-4.5"
    openrouter_referer: str = "https://naikin.xyz"
    openrouter_app_title: str = "naikin-wa-bot"

    owner_wa_number: str = ""
    timezone: str = "Asia/Jakarta"
    work_hours_start: int = 9
    work_hours_end: int = 17
    work_days: str = "mon,tue,wed,thu,fri"
    outreach_per_hour: int = 3
    outreach_interval_minutes: int = 20
    conversation_history_limit: int = 20

    portfolio_url: str = "https://naikin.xyz/"
    business_name: str = "Naikin"

    # Testing: comma-separated whitelist. If empty, all numbers are allowed.
    allowed_numbers: str = ""

    @property
    def work_days_list(self) -> list[str]:
        return [d.strip().lower() for d in self.work_days.split(",") if d.strip()]

    @property
    def allowed_numbers_list(self) -> list[str]:
        return [n.strip() for n in self.allowed_numbers.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Resolve relative SQLite paths against PROJECT_ROOT so it works from any cwd.
    if s.database_url.startswith("sqlite:///./"):
        rel = s.database_url[len("sqlite:///./") :]
        s.database_url = f"sqlite:///{PROJECT_ROOT / rel}"
    return s
