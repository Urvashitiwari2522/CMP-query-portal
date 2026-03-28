"""Configuration settings for the College Query Management Portal backend.

Loads settings from environment variables with sensible defaults for local development.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


def _get_bool(env_value: str | None, default: bool = False) -> bool:
    if env_value is None:
        return default
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """Application configuration loaded from environment variables.

    Attributes:
        SECRET_KEY: Flask secret key used for session signing.
        DATABASE_URI: SQLAlchemy-style URI for SQLite/MySQL, we use raw sqlite3 but keep URI for consistency.
        MAIL_SERVER: SMTP server host.
        MAIL_PORT: SMTP server port.
        MAIL_USERNAME: SMTP username.
        MAIL_PASSWORD: SMTP password or app password.
        MAIL_USE_TLS: Enable TLS.
        MAIL_USE_SSL: Enable SSL (not used with TLS).
        CORS_ORIGINS: Allowed origins for CORS (comma-separated).
    """

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_URI: str = os.getenv("DATABASE_URI", "sqlite:///college_qmp.db")

    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME: str | None = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD: str | None = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS: bool = _get_bool(os.getenv("MAIL_USE_TLS"), True)
    MAIL_USE_SSL: bool = _get_bool(os.getenv("MAIL_USE_SSL"), False)

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")


config = Config()
