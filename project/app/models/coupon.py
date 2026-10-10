from app.extensions import db
from app.models.mixins import utcnow


class DiscountType:
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    ALL = (PERCENTAGE, FIXED)


class Coupon(db.Model):
    """discount_value: whole percent (e.g. 15) for percentage, cents for fixed."""

    __tablename__ = "coupons"
    __table_args__ = (
        db.CheckConstraint("discount_type IN ('percentage', 'fixed')", name="type_valid"),
        db.CheckConstraint("discount_value > 0", name="value_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)  # stored UPPERCASE
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), nullable=False, default=DiscountType.PERCENTAGE)
    discount_value = db.Column(db.Integer, nullable=False)
    minimum_order = db.Column(db.Integer, nullable=False, default=0)  # cents
    maximum_discount = db.Column(db.Integer)  # cents, optional cap
    usage_limit = db.Column(db.Integer)  # None = unlimited
    per_user_limit = db.Column(db.Integer, nullable=False, default=1)
    used_count = db.Column(db.Integer, nullable=False, default=0)
    start_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    usages = db.relationship(
        "CouponUsage", back_populates="coupon", cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def is_expired(self) -> bool:
        return self.expiry_date is not None and self.expiry_date < utcnow()


class CouponUsage(db.Model):
    __tablename__ = "coupon_usages"
    __table_args__ = (db.Index("ix_coupon_usages_coupon_user", "coupon_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(
        db.Integer, db.ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    coupon = db.relationship("Coupon", back_populates="usages")
