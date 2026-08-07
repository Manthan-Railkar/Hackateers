import os
from browser_optimizer.config.settings import Settings, get_settings


def test_default_settings():
    """Verify default fallback parameters in Settings."""
    settings = Settings()
    assert settings.LOG_LEVEL == "INFO"
    assert settings.HEADLESS is True
    assert settings.CACHE_ENABLED is True
    assert settings.CACHE_TTL == 300
    assert settings.BROWSER_TIMEOUT == 30000
    assert settings.SIMILARITY_THRESHOLD == 0.9
    assert settings.CLASSIFICATION_THRESHOLD == 0.65
    assert settings.VISUAL_FALLBACK_THRESHOLD == 3
    assert settings.SQLITE_DB_PATH == "cache.db"


def test_settings_singleton():
    """Verify get_settings() returns a cached singleton instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_custom_env_override(monkeypatch):
    """Verify environment variables override default settings."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("HEADLESS", "false")
    monkeypatch.setenv("BROWSER_TIMEOUT", "60000")
    
    settings = Settings()
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.HEADLESS is False
    assert settings.BROWSER_TIMEOUT == 60000
