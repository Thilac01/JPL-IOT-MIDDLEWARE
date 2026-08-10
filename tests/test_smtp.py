import asyncio
from app.core.config import settings
from app.services.smtp_service import SMTPService

def test_smtp_service_health():
    service = SMTPService()
    health = service.get_health()
    assert isinstance(health, dict)
    assert "enabled" in health
    assert "configured" in health
    assert "emails_sent" in health

def test_smtp_send_suppressed_when_disabled(monkeypatch):
    async def _run():
        service = SMTPService()
        monkeypatch.setattr(settings, "SMTP_ENABLED", False)
        res = await service.send_alert_email("Test Alert Disabled", "Sample message")
        assert res is False

    asyncio.run(_run())

def test_smtp_rate_limiting(monkeypatch):
    async def _run():
        service = SMTPService()
        monkeypatch.setattr(settings, "SMTP_ENABLED", True)
        # Mock last sent time to now
        service.last_sent_time = 9999999999.0
        res = await service.send_alert_email("Test Alert Rate Limit", "Sample message")
        assert res is False

    asyncio.run(_run())
