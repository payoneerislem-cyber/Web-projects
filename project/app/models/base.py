"""Shared model helpers."""
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Naive UTC datetime. SQLite has no tz support, so we store UTC consistently."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
