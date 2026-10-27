"""Admin-editable store settings with config fallbacks. Cached per process for 60 s."""
import time

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Setting

TTL_SECONDS = 60


def _data() -> dict:
    store = current_app.extensions.setdefault("settings_cache", {"at": 0.0, "data": None})
    if store["data"] is None or time.monotonic() - store["at"] > TTL_SECONDS:
        try:
            rows = Setting.query.all()
        except SQLAlchemyError:
            db.session.rollback()
            rows = []
        store["data"] = {row.key: row.value for row in rows}
        store["at"] = time.monotonic()
    return store["data"]


def get(key: str, default=None, allow_empty: bool = False):
    value = _data().get(key)
    if value is None or (value == "" and not allow_empty):
        return default
    return value


def get_int(key: str, default: int) -> int:
    try:
        return int(get(key, default))
    except (TypeError, ValueError):
        return default


def invalidate() -> None:
    current_app.extensions.pop("settings_cache", None)


def save(values: dict) -> None:
    for key, value in values.items():
        Setting.set(key, "" if value is None else value)
    db.session.commit()
    invalidate()
