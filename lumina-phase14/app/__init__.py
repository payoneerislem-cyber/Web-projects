"""Application factory."""
import logging
import os
import secrets

from flask import Flask

from app.extensions import csrf, db, limiter, login_manager, migrate
from config import get_config


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config(config_name))

    _ensure_secret_key(app)
    _ensure_folders(app)
    _configure_logging(app)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)  # batch mode for SQLite ALTERs
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    # Models must be imported so Alembic/SQLAlchemy see them
    from app import models  # noqa: F401

    from app.routes import register_blueprints
    from app.utils.auth_handlers import register_auth_handlers
    from app.utils.context import register_context
    from app.utils.errors import register_error_handlers
    from app.utils.money import format_money
    from app.utils.security import register_security_headers

    register_blueprints(app)
    register_auth_handlers(app)
    register_error_handlers(app)
    register_security_headers(app)
    register_context(app)

    @app.template_filter("money")
    def money_filter(cents):
        return format_money(cents, app.config["CURRENCY_SYMBOL"])

    return app


def _ensure_secret_key(app: Flask) -> None:
    if app.config.get("SECRET_KEY"):
        return
    if app.config["ENV_NAME"] == "production":
        raise RuntimeError("SECRET_KEY must be set in production (.env).")
    # Dev only: random key per process (sessions reset on restart).
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    app.logger.warning("SECRET_KEY not set; using a temporary random key (dev only).")


def _ensure_folders(app: Flask) -> None:
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    app.logger.setLevel(level)
