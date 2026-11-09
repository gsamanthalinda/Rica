import os
import smtplib
from email.message import EmailMessage

from core.config import settings

_sent_emails: list[dict] = []


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    record = {"to": to, "subject": subject, "body": body}
    if html is not None:
        record["html"] = html

    if os.getenv("TESTING") == "1":
        _sent_emails.append(record)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html is not None:
        msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()  # Identify your app to the mail server

        # 2. Upgrade the connection to secure TLS (Crucial for Port 587)
        server.starttls()

        server.ehlo()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def get_sent_emails() -> list[dict]:
    return _sent_emails


def clear_sent_emails() -> None:
    _sent_emails.clear()
