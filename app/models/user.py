from flask import current_app, has_app_context
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow


class Role:
    CUSTOMER = "customer"
    ADMIN = "admin"
    ALL = (CUSTOMER, ADMIN)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('customer', 'admin')", name="role_valid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    role = db.Column(db.String(20), nullable=False, default=Role.CUSTOMER, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)

    addresses = db.relationship(
        "Address", back_populates="user", cascade="all, delete-orphan",
        passive_deletes=True, order_by="Address.id",
    )
    orders = db.relationship(
        "Order", back_populates="user", passive_deletes=True,
        order_by="desc(Order.created_at)",
    )
    reviews = db.relationship(
        "Review", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications = db.relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan",
        passive_deletes=True, order_by="desc(Notification.created_at)",
    )
    cart = db.relationship(
        "Cart", back_populates="user", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )
    wishlist = db.relationship(
        "Wishlist", back_populates="user", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )

    # --- passwords ---
    def set_password(self, password: str) -> None:
        method = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt") if has_app_context() else "scrypt"
        self.password_hash = generate_password_hash(password, method=method)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # --- helpers ---
    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def first_name(self) -> str:
        return (self.name or "").split(" ")[0]

    @property
    def public_name(self) -> str:
        """"Alice M." style name that is safe to show next to a review."""
        parts = (self.name or "").split()
        if len(parts) < 2:
            return parts[0] if parts else "Customer"
        return f"{parts[0]} {parts[-1][0]}."

    def touch_login(self) -> None:
        self.last_login_at = utcnow()

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Address(TimestampMixin, db.Model):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label = db.Column(db.String(50), default="Home")
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False, default="United States")
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="addresses")

    def to_snapshot(self) -> dict:
        """Plain dict stored on Order.shipping_address (immutable copy)."""
        return {
            "full_name": self.full_name, "phone": self.phone,
            "line1": self.line1, "line2": self.line2 or "",
            "city": self.city, "state": self.state or "",
            "postal_code": self.postal_code, "country": self.country,
        }
