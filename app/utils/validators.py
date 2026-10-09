"""Shared validation helpers."""
import re


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def validate_password_strength(password: str) -> list[str]:
    """Return a list of human-readable problems (empty list = password is OK)."""
    errors = []
    if len(password) < 8:
        errors.append("Use at least 8 characters.")
    if len(password) > 128:
        errors.append("Use at most 128 characters.")
    if not re.search(r"[A-Za-z]", password):
        errors.append("Include at least one letter.")
    if not re.search(r"\d", password):
        errors.append("Include at least one number.")
    return errors


def parse_int(value) -> int | None:
    """Strict integer parsing for JSON/form input. Rejects bools, floats and odd digits."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value.strip())
    return None
