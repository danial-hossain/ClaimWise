"""Automated test cases for configuration loading and validation."""

from app.core.config import Settings


def test_settings_defaults():
    """Verify default configuration values."""
    settings = Settings()
    assert settings.app_name == "ClaimWise API"
    assert settings.environment == "development"
    assert settings.api_v1_prefix == "/api/v1"
    assert "http://localhost:3000" in settings.cors_origins


def test_cors_origins_parsing():
    """Verify comma-separated and JSON list CORS parsing."""
    settings_comma = Settings(cors_origins="http://example.com, https://claimwise.app")
    assert "http://example.com" in settings_comma.cors_origins
    assert "https://claimwise.app" in settings_comma.cors_origins

    settings_json = Settings(cors_origins='["https://app.claimwise.com", "http://localhost:3000"]')
    assert "https://app.claimwise.com" in settings_json.cors_origins
    assert "http://localhost:3000" in settings_json.cors_origins
