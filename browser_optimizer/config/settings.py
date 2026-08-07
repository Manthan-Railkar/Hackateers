from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized configuration settings for Browser Optimizer MCP.
    Loads environment variables with fallback defaults.
    """
    LOG_LEVEL: str = "INFO"
    HEADLESS: bool = True
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 300
    CACHE_MAX_SIZE: int = 100
    BROWSER_TIMEOUT: int = 30000
    SIMILARITY_THRESHOLD: float = 0.9
    CLASSIFICATION_THRESHOLD: float = 0.65
    WEBSOCKET_HOST: str = "localhost"
    WEBSOCKET_PORT: int = 8765
    DASHBOARD_PORT: int = 8050
    VISUAL_FALLBACK_THRESHOLD: int = 3
    GROQ_API_KEY: Optional[str] = None
    GROQ_VISION_MODEL: str = "llama-3.2-11b-vision-preview"
    SQLITE_DB_PATH: str = "cache.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of system settings.
    """
    return Settings()
