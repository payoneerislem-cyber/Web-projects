"""Application configuration. All secrets come from environment variables."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    ENV_NAME = "base"
    DEBUG = False
    TESTING = False

    # Secrets (never hardcoded). Validated in create_app().
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        f"sqlite:///{(INSTANCE_DIR / 'store.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Store settings
    STORE_NAME = os.environ.get("STORE_NAME", "Lumina")
    CURRENCY_SYMBOL = "$"
    CURRENCY_CODE = "USD"
    MAX_QTY_PER_ITEM = 10  # per cart line
    FREE_SHIPPING_THRESHOLD = 5000  # cents: orders at or above this ship free
    SHIPPING_FLAT_RATE = 599  # cents
    TAX_RATE = os.environ.get("TAX_RATE", "0")  # e.g. 0.0825 for 8.25%; 0 disables tax
    ANNOUNCEMENT_TEXT = os.environ.get("ANNOUNCEMENT_TEXT", "Free shipping on orders over $50")
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL") or os.environ.get("MAIL_USERNAME") or "support@example.com"
    PER_PAGE_OPTIONS = (12, 24, 48)

    # Sessions & cookies
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PASSWORD_HASH_METHOD = "scrypt"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False

    # CSRF
    WTF_CSRF_TIME_LIMIT = 7200  # seconds

    # Uploads
    UPLOAD_FOLDER = str(BASE_DIR / "app" / "static" / "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # Rate limiting (in-memory storage is fine for local/single-process use)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Mail (optional)
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # Public base URL used to build links in emails (prevents Host-header poisoning)
    SITE_URL = os.environ.get("SITE_URL")

    # Pagination
    PRODUCTS_PER_PAGE = 12


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True


class TestingConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"  # fast hashing keeps the test suite quick
    SECRET_KEY = "test-only-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    ENV_NAME = "production"
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[Config]:
    name = name or os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "development"
    try:
        return CONFIG_MAP[name.lower()]
    except KeyError:
        raise RuntimeError(
            f"Unknown config '{name}'. Use one of: {', '.join(CONFIG_MAP)}"
        ) from None
