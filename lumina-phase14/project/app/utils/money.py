"""Money helpers. Prices are stored as integer cents to avoid float errors."""
from decimal import ROUND_HALF_UP, Decimal


def to_cents(value) -> int:
    """Convert a user-entered amount ('19.99', 19.99, Decimal) to integer cents.

    Raises ValueError for anything that isn't a finite number.
    """
    try:
        amount = Decimal(str(value).strip())
        if not amount.is_finite():
            raise ValueError
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (ArithmeticError, AttributeError, ValueError):
        raise ValueError(f"Invalid amount: {value!r}") from None


def format_money(cents, symbol: str = "$") -> str:
    cents = int(cents or 0)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{symbol}{cents // 100:,}.{cents % 100:02d}"
