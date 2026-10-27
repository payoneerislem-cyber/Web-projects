"""Email sending. Without MAIL_SERVER, messages are printed to the console (dev)."""
import smtplib
from email.message import EmailMessage

from flask import current_app


def _one_line(value: str) -> str:
    """Collapse whitespace/newlines so user input can't inject extra headers."""
    return " ".join((value or "").split())


def send_email(to: str, subject: str, body: str, reply_to: str | None = None) -> bool:
    cfg = current_app.config
    subject = _one_line(subject)
    reply_to = _one_line(reply_to) if reply_to else None

    if not cfg.get("MAIL_SERVER"):
        if cfg["ENV_NAME"] == "production":
            current_app.logger.warning("MAIL_SERVER not configured; email to %s not sent.", to)
            return False
        current_app.logger.warning(
            "\n===== [DEV EMAIL] =====\nTo: %s\nReply-To: %s\nSubject: %s\n\n%s\n=======================",
            to, reply_to or "-", subject, body,
        )
        return True

    msg = EmailMessage()
    msg["From"] = cfg.get("MAIL_USERNAME") or "no-reply@localhost"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
            smtp.starttls()
            if cfg.get("MAIL_USERNAME"):
                smtp.login(cfg["MAIL_USERNAME"], cfg.get("MAIL_PASSWORD") or "")
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError, ValueError):
        current_app.logger.exception("Failed to send email to %s", to)
        return False
