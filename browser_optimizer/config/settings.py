"""
Configuration settings module for the Browser Optimizer MCP.
Loads environment variables from .env file and sets defaults.
"""

from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    """
    Settings container managing settings values loaded from env.
    Provides sane defaults for logging, browser execution, caching, and timeouts.
    """
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    HEADLESS = os.getenv("HEADLESS", "True").strip().lower() in ("true", "1", "yes")
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").strip().lower() in ("true", "1", "yes")
    CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
    CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "100"))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30000"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.9"))
    CLASSIFICATION_THRESHOLD = float(os.getenv("CLASSIFICATION_THRESHOLD", "0.65"))
    WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "localhost")
    WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "8765"))
    DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8050"))
    AUTO_OPEN_DASHBOARD = os.getenv("AUTO_OPEN_DASHBOARD", "True").strip().lower() in ("true", "1", "yes")
    VISUAL_FALLBACK_THRESHOLD = int(os.getenv("VISUAL_FALLBACK_THRESHOLD", "3"))
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")

    # MCP 2026-07-28 Protocol Settings
    MCP_PROTOCOL_VERSION = os.getenv("MCP_PROTOCOL_VERSION", "2026-07-28")
    TOOLS_LIST_TTL_MS = int(os.getenv("TOOLS_LIST_TTL_MS", "300000"))  # 5 minutes
    TOOLS_LIST_CACHE_SCOPE = os.getenv("TOOLS_LIST_CACHE_SCOPE", "public")

    # DOM Checkpointing & Recovery Settings
    ENABLE_CHECKPOINTING = os.getenv("ENABLE_CHECKPOINTING", "True").strip().lower() in ("true", "1", "yes")
    MAX_CHECKPOINTS = int(os.getenv("MAX_CHECKPOINTS", "20"))
    CHECKPOINT_INTERVAL = int(os.getenv("CHECKPOINT_INTERVAL", "1000"))  # ms
    CHECKPOINT_RETENTION_DAYS = int(os.getenv("CHECKPOINT_RETENTION_DAYS", "7"))
    MINIMUM_RESUME_CONFIDENCE = float(os.getenv("MINIMUM_RESUME_CONFIDENCE", "0.70"))
    ASYNC_CHECKPOINTING = os.getenv("ASYNC_CHECKPOINTING", "True").strip().lower() in ("true", "1", "yes")

    # LLM-Aware Website Discovery (llms.txt) Settings
    ENABLE_LLMS_DISCOVERY = os.getenv("ENABLE_LLMS_DISCOVERY", "True").strip().lower() in ("true", "1", "yes")
    LLMS_CACHE_TTL = int(os.getenv("LLMS_CACHE_TTL", "86400"))  # 24 hours
    ENABLE_DIRECT_FETCH = os.getenv("ENABLE_DIRECT_FETCH", "True").strip().lower() in ("true", "1", "yes")
    FALLBACK_TO_BROWSER = os.getenv("FALLBACK_TO_BROWSER", "True").strip().lower() in ("true", "1", "yes")
    ALLOW_HYBRID_NAVIGATION = os.getenv("ALLOW_HYBRID_NAVIGATION", "True").strip().lower() in ("true", "1", "yes")
    MAX_LLMS_SIZE = int(os.getenv("MAX_LLMS_SIZE", "1048576"))  # 1MB



# Instantiated settings for export
settings = Settings()