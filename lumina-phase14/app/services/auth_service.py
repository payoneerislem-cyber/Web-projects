"""Authentication business logic: registration, credentials, password reset."""
import hashlib
import hmac

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User
from app.services.email_service import send_email
from app.services.notification_service import notify
from app.utils.validators import normalize_email

RESET_TOKEN_MAX_AGE = 30 * 60  # seconds
_DUMMY_HASH = generate_password_hash("timing-equalizer-password")


class AuthError(Exception):
    """A user-facing authentication problem."""


# ---------- registration / login ----------
def register_user(name: str, email: str, password: str) -> User:
    email = normalize_email(email)
    if User.query.filter_by(email=email).first():
        raise AuthError("An account with this email already exists.")
    user = User(name=name.strip(), email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.flush()
        notify(user.id, "welcome", "Welcome!", "Your account has been created.")
        db.session.commit()
    except IntegrityError:  # race: same email registered concurrently
        db.session.rollback()
        raise AuthError("An account with this email already exists.") from None
    return user


def authenticate(email: str, password: str) -> User | None:
    """Return the user on success, None on bad credentials.

    Raises AuthError only after the password was verified (so it can't be used
    to discover which emails are registered).
    """
    user = User.query.filter_by(email=normalize_email(email)).first()
    if user is None:
        check_password_hash(_DUMMY_HASH, password)  # keep timing similar
        return None
    if not user.check_password(password):
        return None
    if not user.is_active:
        raise AuthError("This account has been disabled. Please contact support.")
    return user


# ---------- password reset ----------
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def _fingerprint(user: User) -> str:
    """Changes whenever the password changes, which makes tokens single-use."""
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def generate_reset_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "fp": _fingerprint(user)})


def verify_reset_token(token: str, max_age: int = RESET_TOKEN_MAX_AGE) -> User | None:
    try:
        data = _serializer().loads(token, max_age=max_age)
        user = db.session.get(User, int(data["uid"]))
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
    if user is None or not user.is_active:
        return None
    if not hmac.compare_digest(data.get("fp", ""), _fingerprint(user)):
        return None
    return user


def request_password_reset(email: str) -> None:
    """Send a reset link if the account exists. Callers must not reveal the result."""
    user = User.query.filter_by(email=normalize_email(email)).first()
    if user is None or not user.is_active:
        return
    link = url_for("auth.reset_password", token=generate_reset_token(user), _external=True)
    minutes = RESET_TOKEN_MAX_AGE // 60
    send_email(
        user.email,
        f"Reset your {current_app.config['STORE_NAME']} password",
        f"Hi {user.first_name},\n\nUse this link to choose a new password "
        f"(valid for {minutes} minutes):\n{link}\n\n"
        "If you didn't request this, you can safely ignore this email.",
    )


def reset_password(user: User, new_password: str) -> None:
    user.set_password(new_password)
    notify(user.id, "security", "Password changed",
           "Your password was changed. If this wasn't you, contact support.")
    db.session.commit()
