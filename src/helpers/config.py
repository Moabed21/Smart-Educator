import json
from functools import lru_cache
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        validate_assignment=True,
        env_file=(".env", "src/.env"),
        extra="ignore",
    )

    # Core Application Settings
    APP_NAME: str = "smart-educator"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Security & Access Control
    API_KEY: str | None = None
    CORS_ORIGINS: list[str] = ["*"]

    # File Ingestion Limits
    FILE_MAX_SIZE: int = 10  # MB
    FILE_DEFAULT_CHUNK_SIZE: int = 512000  # 512 KB
    FILE_ALLOWED_TYPES: list[str] = ["text/plain", "application/json", "application/pdf"]

    # AI & LLM Provider (Google Gemini)
    GEMINI_API_KEY: str

    # PostgreSQL Database Settings & Pool Tuning
    DATABASE_URL: str
    DB_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # Redis Cache Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_TTL: int = 86400

    # ChromaDB Vector Database Settings
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_COLLECTION_NAME: str = "questions"

    @field_validator("FILE_ALLOWED_TYPES", "CORS_ORIGINS", mode="before")
    @classmethod
    def parse_string_to_list(cls, value: Any) -> list[str]:
        """Allow lists to be provided as JSON arrays or comma-separated strings in .env."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Reads and validates environment configurations once per process."""
    return Settings()