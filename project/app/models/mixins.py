from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Naive UTC datetime (SQLite doesn't store timezones)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
