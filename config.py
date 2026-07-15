# config.py
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables.

    All values are read from a .env file at startup via pydantic-settings.
    Never hardcode secrets — add them to .env and reference them here.
    """

    # Database
    database_url: str

    # LLM
    gemini_api_key: str

    # GitHub
    github_pat: str

    # Add this to the Settings class
    gcp_project_id: str | None = None

    # Pipeline behaviour
    default_lookback_minutes: int = 30
    max_log_size_bytes: int = 10 * 1024 * 1024  # 10MB

    # High-risk file patterns for deploy correlation
    high_risk_file_patterns: list[str] = [
        ".yaml",
        ".yml",
        ".env",
        "migration",
        "auth",
        "config",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()