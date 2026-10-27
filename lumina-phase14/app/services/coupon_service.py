"""Coupon validation and discount maths. Amounts are integer cents."""
from decimal import ROUND_HALF_UP, Decimal

from flask import current_app
from sqlalchemy import case, update

from app.extensions import db
from app.models import Coupon, CouponUsage
from app.models.mixins import utcnow
from app.utils.money import format_money


class CouponError(Exception):
    """The coupon can't be used; the message says why."""


def normalize(code) -> str:
    return " ".join(str(code or "").split()).upper()[:50]


def discount_amount(coupon: Coupon, subtotal: int) -> int:
    if coupon.discount_type == "percentage":
        raw = int((Decimal(subtotal) * coupon.discount_value / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        raw = coupon.discount_value
    if coupon.maximum_discount is not None:
        raw = min(raw, coupon.maximum_discount)
    return max(0, min(raw, subtotal))  # never more than the goods cost


def validate(code, subtotal: int, user=None) -> Coupon:
    """Return the coupon if it can be used for this subtotal, else raise CouponError."""
    code = normalize(code)
    if not code:
        raise CouponError("Enter a coupon code.")
    coupon = Coupon.query.filter_by(code=code).first()
    if coupon is None or not coupon.is_active:
        raise CouponError("That coupon code isn't valid.")
    now = utcnow()
    if coupon.start_date and coupon.start_date > now:
        raise CouponError("This coupon isn't active yet.")
    if coupon.expiry_date and coupon.expiry_date < now:
        raise CouponError("This coupon has expired.")
    if subtotal < coupon.minimum_order:
        symbol = current_app.config["CURRENCY_SYMBOL"]
        raise CouponError(f"This coupon needs a minimum order of {format_money(coupon.minimum_order, symbol)}.")
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise CouponError("This coupon has reached its usage limit.")
    if user is not None and getattr(user, "is_authenticated", False):
        used = CouponUsage.query.filter_by(coupon_id=coupon.id, user_id=user.id).count()
        if used >= coupon.per_user_limit:
            raise CouponError("You've already used this coupon.")
    return coupon


def release(order) -> None:
    """Give a coupon use back when its order is cancelled or refunded (no commit)."""
    if not order.coupon_code:
        return
    usage = CouponUsage.query.filter_by(order_id=order.id).first()
    if usage is None:
        return
    db.session.delete(usage)
    db.session.execute(
        update(Coupon).where(Coupon.id == usage.coupon_id)
        .values(used_count=case((Coupon.used_count > 0, Coupon.used_count - 1), else_=0))
        .execution_options(synchronize_session=False))
