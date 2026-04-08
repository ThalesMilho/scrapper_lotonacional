"""
config/settings.py
──────────────────
Single source of truth for all runtime configuration.
Values are loaded from environment variables / .env file via Pydantic.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Runtime
    scraper_mode: str = Field("oneshot", alias="SCRAPER_MODE")
    scraper_debug: bool = Field(False, alias="SCRAPER_DEBUG")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_file: str = Field("logs/scraper.log", alias="LOG_FILE")

    # ── Network / Proxy
    http_proxy: Optional[str] = Field(None, alias="HTTP_PROXY")
    https_proxy: Optional[str] = Field(None, alias="HTTPS_PROXY")

    # ── Retry
    retry_interval_seconds: int = Field(30, alias="SCRAPER_RETRY_INTERVAL_SECONDS")
    retry_max_minutes: int = Field(15, alias="SCRAPER_RETRY_MAX_MINUTES")

    # ── Schedules (stored as comma-separated strings in .env)
    schedule_nacional_raw: str = Field("11:30,14:30,19:30", alias="SCHEDULE_NACIONAL")
    schedule_resultado_facil_raw: str = Field(
        "09:30,11:30,14:30,16:30,18:30,21:30,23:30",
        alias="SCHEDULE_RESULTADO_FACIL",
    )

    # ── Webhook (outbound → maiorbichoo.com)
    webhook_url: str = Field("http://localhost:9999/stub", alias="WEBHOOK_URL")
    webhook_api_key: str = Field("change-me", alias="WEBHOOK_API_KEY")

    # ── FastAPI (inbound endpoints)
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8080, alias="API_PORT")
    api_secret_key: str = Field("change-me-api-key", alias="API_SECRET_KEY")

    # ── Storage
    storage_json_path: str = Field("data/results.json", alias="STORAGE_JSON_PATH")
    storage_csv_path: str = Field("data/results.csv", alias="STORAGE_CSV_PATH")

    # ── Computed helpers (not env fields)
    @property
    def schedule_nacional(self) -> List[str]:
        return [t.strip() for t in self.schedule_nacional_raw.split(",") if t.strip()]

    @property
    def schedule_resultado_facil(self) -> List[str]:
        return [t.strip() for t in self.schedule_resultado_facil_raw.split(",") if t.strip()]

    @property
    def proxies(self) -> Optional[dict]:
        if self.http_proxy or self.https_proxy:
            return {
                "http://": self.http_proxy or self.https_proxy,
                "https://": self.https_proxy or self.http_proxy,
            }
        return None

    @field_validator("log_level")
    @classmethod
    def normalise_log_level(cls, v: str) -> str:
        return v.upper()

    def ensure_dirs(self) -> None:
        """Create output directories if they do not exist."""
        for p in [self.storage_json_path, self.storage_csv_path, self.log_file]:
            Path(p).parent.mkdir(parents=True, exist_ok=True)


# Singleton
settings = Settings()
settings.ensure_dirs()
