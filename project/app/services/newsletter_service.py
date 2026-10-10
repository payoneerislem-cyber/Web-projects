from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import NewsletterSubscriber
from app.utils.validators import normalize_email


def subscribe(email: str) -> bool:
    """Subscribe an address. Returns False if it was already subscribed."""
    email = normalize_email(email)
    if NewsletterSubscriber.query.filter_by(email=email).first():
        return False
    db.session.add(NewsletterSubscriber(email=email))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False
    return True
