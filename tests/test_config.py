from app.core.config import Settings

def test_config_defaults():
    settings = Settings()
    assert settings.APP_NAME == "JPL Security & IoT Middleware"
    assert settings.APP_PORT == 8000
    assert settings.CDC_SERVER_ID == 100
    assert isinstance(settings.CORS_ORIGINS, list)

def test_cors_parsing():
    settings = Settings(CORS_ORIGINS="http://localhost:3000, https://library.example.com")
    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "https://library.example.com" in settings.CORS_ORIGINS

def test_cors_json_parsing():
    settings = Settings(CORS_ORIGINS='["http://localhost:8000", "http://127.0.0.1:8000"]')
    assert len(settings.CORS_ORIGINS) == 2
    assert "http://localhost:8000" in settings.CORS_ORIGINS

def test_production_flag():
    settings_prod = Settings(ENVIRONMENT="production")
    assert settings_prod.is_production is True
    settings_dev = Settings(ENVIRONMENT="development")
    assert settings_dev.is_production is False
