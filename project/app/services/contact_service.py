from flask import current_app

from app.services.email_service import send_email


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def send_contact_message(name: str, email: str, subject: str, message: str) -> bool:
    cfg = current_app.config
    recipient = cfg.get("CONTACT_EMAIL") or cfg.get("MAIL_USERNAME") or "support@localhost"
    body = f"From: {_clean(name)} <{_clean(email)}>\n\n{message}"
    return send_email(recipient, f"[Contact] {_clean(subject)}", body, reply_to=_clean(email))
