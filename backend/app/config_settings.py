# =============================================================================
# config_settings.py
# Application settings loaded from environment variables / .env file.
#
# Postgres-only. The app fails fast at startup if DATABASE_URL or SECRET_KEY
# are missing, so a misconfigured environment can never silently fall back
# to a local SQLite file (which historically caused users to "vanish" when
# the container restarted on Railway).
# =============================================================================

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    # No default. If DATABASE_URL is missing the app refuses to boot — far
    # better than silently writing data to ephemeral container storage.
    # Railway's Postgres add-on injects this variable automatically; the
    # backend service just needs to "reference" it under Variables.
    database_url: str

    # ── Auth ────────────────────────────────────────────────────────────────
    # No default. Generate a real random key and set it on Railway:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    # then in Railway → backend service → Variables → SECRET_KEY = <output>
    secret_key: str
    algorithm: str = "HS256"

    # JWT lifetime in minutes (8 hours by default). Tokens automatically
    # expire after this period, requiring the user to log in again.
    access_token_expire_minutes: int = 480

    # ── Environment ─────────────────────────────────────────────────────────
    environment: str = "development"
    allowed_origins: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# ── Hard runtime checks ────────────────────────────────────────────────────
# Fail loudly rather than silently falling back to bad defaults. If either
# of these triggers, fix the env var on Railway (or in your local .env)
# rather than weakening the check.
if not settings.database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg")):
    raise RuntimeError(
        f"DATABASE_URL must point at a PostgreSQL instance. "
        f"Got: {settings.database_url[:30]}... "
        f"Set DATABASE_URL on Railway (Backend service → Variables tab → "
        f"reference the Postgres add-on) or in your local .env."
    )

if (settings.secret_key == "change-this-in-production-min-32-chars"
        or len(settings.secret_key) < 32):
    raise RuntimeError(
        "SECRET_KEY is missing, default, or too short. Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
        "and set it on Railway (Backend service → Variables → SECRET_KEY)."
    )
