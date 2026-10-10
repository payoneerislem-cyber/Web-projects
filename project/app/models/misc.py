from app.extensions import db
from app.models.mixins import utcnow


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (db.Index("ix_notifications_user_read", "user_id", "is_read"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type = db.Column(db.String(30), nullable=False, default="info")
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(500))
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")


class Setting(db.Model):
    """Key/value store for admin-editable store settings (shipping, tax...)."""

    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)

    @classmethod
    def get(cls, key: str, default=None):
        row = db.session.get(cls, key)
        return row.value if row is not None else default

    @classmethod
    def set(cls, key: str, value) -> None:
        """Stage a change; the caller commits."""
        row = db.session.get(cls, key)
        if row is None:
            db.session.add(cls(key=key, value=str(value)))
        else:
            row.value = str(value)


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
