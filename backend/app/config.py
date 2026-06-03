"""
Application configuration using pydantic-settings.
All values can be overridden via environment variables or .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://visionretail:visionretail_secret@localhost:5435/visionretail"
    )

    # ── OpenAI / GPT ────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"
    openai_base_url: str | None = None
    openai_max_tokens: int = 1024
    openai_timeout_seconds: int = 30

    # ── App ─────────────────────────────────────────────────────────
    environment: str = "production"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── CV Pipeline ──────────────────────────────────────────────────
    yolo_model: str = "yolov8m.pt"
    yolo_confidence: float = 0.35
    yolo_iou: float = 0.45
    reid_threshold: float = 0.65
    reid_reentry_window_minutes: int = 30
    staff_confidence_threshold: float = 0.75

    # ── Business Rules ───────────────────────────────────────────────
    conversion_window_minutes: int = 5
    queue_density_threshold: int = 3          # persons → queue active
    queue_abandon_dwell_seconds: int = 120    # 2 min dwell without tx → abandon
    anomaly_zscore_high: float = 2.5
    anomaly_zscore_critical: float = 3.0
    anomaly_lookback_days: int = 1

    # ── Store defaults ───────────────────────────────────────────────
    default_store_id: str = "STORE_BLR_002"
    default_timezone: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()
