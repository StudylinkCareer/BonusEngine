# =============================================================================
# config_settings.py
# Application settings loaded from environment variables / .env file.
# =============================================================================

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "sqlite:///./bonusengine.db"
    secret_key: str = "change-this-in-production-min-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    environment: str = "development"
    allowed_origins: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
