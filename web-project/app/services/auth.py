import secrets
import time

from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories import UserRepository


def normalize_email(email):
    return (email or "").strip().lower()


def validate_registration(username, password, email):
    username = (username or "").strip()
    email = normalize_email(email)

    if len(username) < 3:
        return False, "Username must contain at least 3 characters."
    if len(password or "") < 8:
        return False, "Password must contain at least 8 characters."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."
    return True, None


def register_user(username, password, email):
    valid, error = validate_registration(username, password, email)
    if not valid:
        return None, error

    if UserRepository.get_by_username(username):
        return None, "Username already exists."
    if UserRepository.get_by_email(email):
        return None, "Email already exists."

    user_id = UserRepository.create(username, generate_password_hash(password), email)
    return user_id, None


def authenticate(username, password):
    user = UserRepository.get_by_username((username or "").strip())
    if user and check_password_hash(user["password"], password or ""):
        return user
    return None


def change_password(user_id, old_password, new_password):
    user = UserRepository.get_by_id(user_id)
    if not user or not check_password_hash(user["password"], old_password or ""):
        return False, "Old password is incorrect."
    if len(new_password or "") < 8:
        return False, "New password must contain at least 8 characters."
    UserRepository.update_password(user_id, generate_password_hash(new_password))
    return True, "Password updated successfully."


def generate_otp():
    return f"{secrets.randbelow(900000) + 100000:06d}"


def otp_expiration(ttl_seconds):
    return time.time() + ttl_seconds


def is_otp_valid(expected, supplied, expires_at):
    try:
        return bool(expected and supplied and expected == supplied and time.time() <= float(expires_at))
    except (TypeError, ValueError):
        return False
