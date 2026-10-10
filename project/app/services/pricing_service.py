"""Shipping, tax and order totals. All amounts are integer cents."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import current_app


def shipping_cost(amount_after_discount: int, threshold: int, flat_rate: int) -> int:
    if amount_after_discount <= 0 or amount_after_discount >= threshold:
        return 0
    return flat_rate


def tax_amount(taxable: int, rate) -> int:
    try:
        factor = Decimal(str(rate))
    except InvalidOperation:
        return 0
    if factor <= 0 or taxable <= 0:
        return 0
    return int((Decimal(taxable) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate(subtotal: int, discount: int = 0) -> dict:
    """Totals for a cart or order. `discount` is the coupon amount in cents."""
    cfg = current_app.config
    discount = max(0, min(int(discount), subtotal))
    after_discount = subtotal - discount
    threshold = cfg["FREE_SHIPPING_THRESHOLD"]
    shipping = shipping_cost(after_discount, threshold, cfg["SHIPPING_FLAT_RATE"])
    tax = tax_amount(after_discount, cfg["TAX_RATE"])
    return {
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "tax": tax,
        "total": after_discount + shipping + tax,
        "free_shipping_threshold": threshold,
        "free_shipping_remaining": max(threshold - after_discount, 0) if subtotal > 0 else threshold,
    }
