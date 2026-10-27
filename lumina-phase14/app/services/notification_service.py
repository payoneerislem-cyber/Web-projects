"""Notification helpers (expanded in Phase 16)."""
from app.extensions import db
from app.models import Notification


def notify(user_id: int, type_: str, title: str, message: str | None = None,
           link: str | None = None) -> Notification:
    """Stage a notification; the caller commits."""
    notification = Notification(user_id=user_id, type=type_, title=title,
                                message=message, link=link)
    db.session.add(notification)
    return notification
