"""Shipping, tax and order totals. All amounts are integer cents."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import current_app

from app.services import settings_service
from app.utils.money import format_money

DEFAULT_SHIPPING_METHOD = "standard"
SHIPPING_METHODS = {
    "standard": {"label": "Standard delivery", "eta": "2-4 business days"},
    "express": {"label": "Express delivery", "eta": "1-2 business days"},
}


def shipping_cost(amount_after_discount: int, threshold: int, flat_rate: int) -> int:
    if amount_after_discount <= 0 or amount_after_discount >= threshold:
        return 0
    return flat_rate


def shipping_for(method: str, amount_after_discount: int) -> int:
    if method not in SHIPPING_METHODS:
        raise ValueError(f"Unknown shipping method: {method!r}")
    cfg = current_app.config
    if amount_after_discount <= 0:
        return 0
    if method == "express":  # express is never free
        return settings_service.get_int("express_shipping_rate", cfg["EXPRESS_SHIPPING_RATE"])
    return shipping_cost(amount_after_discount,
                         settings_service.get_int("free_shipping_threshold", cfg["FREE_SHIPPING_THRESHOLD"]),
                         settings_service.get_int("standard_shipping_rate", cfg["SHIPPING_FLAT_RATE"]))


def tax_amount(taxable: int, rate) -> int:
    try:
        factor = Decimal(str(rate))
    except InvalidOperation:
        return 0
    if factor <= 0 or taxable <= 0:
        return 0
    return int((Decimal(taxable) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate(subtotal: int, discount: int = 0, method: str = DEFAULT_SHIPPING_METHOD) -> dict:
    """Totals for a cart or order. `discount` is the coupon amount in cents."""
    cfg = current_app.config
    discount = max(0, min(int(discount), subtotal))
    after_discount = subtotal - discount
    threshold = settings_service.get_int("free_shipping_threshold", cfg["FREE_SHIPPING_THRESHOLD"])
    shipping = shipping_for(method, after_discount)
    tax = tax_amount(after_discount, settings_service.get("tax_rate", cfg["TAX_RATE"]))
    return {
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "tax": tax,
        "total": after_discount + shipping + tax,
        "shipping_method": method,
        "free_shipping_threshold": threshold,
        "free_shipping_remaining": max(threshold - after_discount, 0) if subtotal > 0 else threshold,
    }


def shipping_options(subtotal: int, discount: int = 0) -> list:
    """Every delivery option with its cost and the resulting order total (for checkout)."""
    symbol = current_app.config["CURRENCY_SYMBOL"]
    options = []
    for key, info in SHIPPING_METHODS.items():
        totals = calculate(subtotal, discount, key)
        options.append({
            "key": key, "label": info["label"], "eta": info["eta"],
            "shipping": totals["shipping"],
            "shipping_formatted": "Free" if totals["shipping"] == 0 else format_money(totals["shipping"], symbol),
            "total": totals["total"],
            "total_formatted": format_money(totals["total"], symbol),
        })
    return options
