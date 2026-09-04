from app.core.config import Settings


def test_settings_default_values() -> None:
    """Verify default configuration attributes."""
    settings = Settings(
        APP_NAME="TestBazaar",
        APP_ENV="testing",
        JWT_SECRET_KEY="test-secret-key-32chars-minimum-needed",
    )
    assert settings.APP_NAME == "TestBazaar"
    assert settings.is_testing is True
    assert settings.is_production is False


def test_cors_origins_parsing() -> None:
    """Verify flexible parsing of ALLOWED_ORIGINS."""
    # From comma-separated string
    s1 = Settings(
        JWT_SECRET_KEY="test-secret-key-32chars-minimum-needed",
        ALLOWED_ORIGINS="http://localhost:3000, https://example.com",
    )
    assert s1.ALLOWED_ORIGINS == ["http://localhost:3000", "https://example.com"]

    # From JSON array string
    s2 = Settings(
        JWT_SECRET_KEY="test-secret-key-32chars-minimum-needed",
        ALLOWED_ORIGINS='["http://localhost:3000", "https://app.example.com"]',
    )
    assert s2.ALLOWED_ORIGINS == ["http://localhost:3000", "https://app.example.com"]

    # From Python list
    s3 = Settings(
        JWT_SECRET_KEY="test-secret-key-32chars-minimum-needed",
        ALLOWED_ORIGINS=["http://localhost:3000"],
    )
    assert s3.ALLOWED_ORIGINS == ["http://localhost:3000"]
