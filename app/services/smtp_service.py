import asyncio
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
from app.core.config import settings

logger = logging.getLogger("services.smtp")

class SMTPService:
    def __init__(self):
        self.last_sent_time: float = 0.0
        self.emails_sent_count: int = 0
        self.failed_emails_count: int = 0
        self.last_error: Optional[str] = None
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(
            settings.SMTP_ENABLED and
            settings.SMTP_SERVER and
            settings.SMTP_USER and
            settings.SMTP_PASSWORD and
            settings.NOTIFICATION_EMAIL
        )

    async def send_alert_email(
        self,
        subject: str,
        message: str,
        level: str = "info",
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Asynchronously send an alert email with rate-limiting protection."""
        if not self.is_configured():
            return False

        async with self._lock:
            # Rate limit check
            current_time = time.time()
            if (current_time - self.last_sent_time) < settings.SMTP_RATE_LIMIT_SECONDS:
                logger.debug(f"SMTP rate limit hit. Suppressing email: {subject}")
                return False
            self.last_sent_time = current_time

        def _send_sync() -> bool:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"[{settings.APP_NAME}] {subject}"
                msg["From"] = settings.SMTP_USER
                msg["To"] = settings.NOTIFICATION_EMAIL

                # Level color accents
                level_colors = {
                    "success": "#28a745",
                    "info": "#007bff",
                    "warning": "#ffc107",
                    "danger": "#dc3545",
                    "error": "#dc3545"
                }
                accent_color = level_colors.get(level.lower(), "#007bff")

                # HTML Email Template
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
                        .header {{ background-color: #1a1f2c; color: #ffffff; padding: 20px 24px; border-left: 6px solid {accent_color}; }}
                        .header h2 {{ margin: 0; font-size: 18px; font-weight: 600; }}
                        .content {{ padding: 24px; }}
                        .alert-box {{ background-color: #f8f9fa; border-left: 4px solid {accent_color}; padding: 16px; border-radius: 4px; margin-bottom: 20px; }}
                        .details-table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
                        .details-table th, .details-table td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e9ecef; }}
                        .details-table th {{ background-color: #f8f9fa; font-weight: 600; color: #495057; }}
                        .footer {{ background-color: #f8f9fa; padding: 16px 24px; font-size: 12px; color: #868e96; text-align: center; border-top: 1px solid #e9ecef; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>{subject}</h2>
                        </div>
                        <div class="content">
                            <div class="alert-box">
                                <p style="margin: 0; font-size: 15px; line-height: 1.5;">{message}</p>
                            </div>
                """

                if details:
                    html_content += """
                            <table class="details-table">
                                <thead>
                                    <tr><th>Attribute</th><th>Value</th></tr>
                                </thead>
                                <tbody>
                    """
                    for k, v in details.items():
                        html_content += f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
                    html_content += """
                                </tbody>
                            </table>
                    """

                html_content += f"""
                        </div>
                        <div class="footer">
                            <p style="margin: 0;">Sent automatically by {settings.APP_NAME} v{settings.APP_VERSION}</p>
                        </div>
                    </div>
                </body>
                </html>
                """

                # Attach text and HTML parts
                part_text = MIMEText(f"{subject}\n\n{message}\n\nDetails: {details or 'None'}", "plain")
                part_html = MIMEText(html_content, "html")
                msg.attach(part_text)
                msg.attach(part_html)

                # Connect and send
                server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=10)
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, settings.NOTIFICATION_EMAIL, msg.as_string())
                server.quit()

                self.emails_sent_count += 1
                self.last_error = None
                logger.info(f"Alert email sent successfully to {settings.NOTIFICATION_EMAIL}: {subject}")
                return True
            except Exception as e:
                self.failed_emails_count += 1
                self.last_error = str(e)
                logger.error(f"Failed to send alert email: {e}")
                return False

        return await asyncio.to_thread(_send_sync)

    def get_health(self) -> Dict[str, Any]:
        return {
            "enabled": settings.SMTP_ENABLED,
            "configured": self.is_configured(),
            "server": settings.SMTP_SERVER if settings.SMTP_ENABLED else None,
            "port": settings.SMTP_PORT if settings.SMTP_ENABLED else None,
            "recipient": settings.NOTIFICATION_EMAIL if settings.SMTP_ENABLED else None,
            "emails_sent": self.emails_sent_count,
            "emails_failed": self.failed_emails_count,
            "last_error": self.last_error
        }

# Global singleton
smtp_service = SMTPService()
