import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name, default):
    raw = os.getenv(name)
    path = Path(raw) if raw else Path(default)
    return (BASE_DIR / path).resolve() if not path.is_absolute() else path.resolve()


def get_config():
    environment = os.getenv("APP_ENV", "development").strip().lower()
    production = environment == "production"

    return {
        "ENVIRONMENT": environment,
        "DEBUG": _env_bool("FLASK_DEBUG", False) if not production else False,
        "TESTING": False,
        "SECRET_KEY": os.getenv("SECRET_KEY", "change-this-secret-key-in-production"),
        "DATABASE_PATH": _env_path("DATABASE_PATH", INSTANCE_DIR / "budget_tracker.db"),
        "UPLOAD_FOLDER": _env_path("UPLOAD_FOLDER", BASE_DIR / "app" / "static" / "uploads"),
        "PERMANENT_SESSION_LIFETIME": timedelta(days=30),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": True if production else _env_bool("SESSION_COOKIE_SECURE", False),
        "MAX_CONTENT_LENGTH": int(os.getenv("MAX_CONTENT_LENGTH", str(5 * 1024 * 1024))),
        "MAIL_SERVER": os.getenv("MAIL_SERVER", "smtp.gmail.com"),
        "MAIL_PORT": int(os.getenv("MAIL_PORT", "587")),
        "MAIL_USERNAME": os.getenv("MAIL_USERNAME", ""),
        "MAIL_PASSWORD": os.getenv("MAIL_PASSWORD", ""),
        "MAIL_USE_TLS": _env_bool("MAIL_USE_TLS", True),
        "MAIL_SENDER": os.getenv("MAIL_SENDER", ""),
        "OTP_TTL_SECONDS": int(os.getenv("OTP_TTL_SECONDS", "600")),
        "TRUST_PROXY": _env_bool("TRUST_PROXY", False),
    }
