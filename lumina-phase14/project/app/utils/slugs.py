"""Slug helpers."""
import re
import unicodedata

from app.extensions import db


def slugify(text: str, max_length: int = 120) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_length].strip("-") or "item"


def unique_slug(model, text: str, exclude_id: int | None = None) -> str:
    """Return a slug for `text` that is not yet used in `model.slug`."""
    base = slugify(text)
    slug, n = base, 2
    while True:
        query = db.session.query(model.id).filter(model.slug == slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{n}"
        n += 1
