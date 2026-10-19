"""Application factory for Budget Tracker."""

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import BASE_DIR, get_config
from .db.database import init_database
from .utils.csrf import init_csrf


def create_app(config_class=None):
    """Create, configure, and initialize the Flask application.

    ``get_config()`` returns a mapping, while callers may also provide a
    normal Flask configuration object/class. Support both forms explicitly.
    """
    load_dotenv(BASE_DIR / ".env")

    app = Flask(__name__, instance_relative_config=True)
    config_source = config_class if config_class is not None else get_config()

    if isinstance(config_source, dict):
        app.config.from_mapping(config_source)
    else:
        app.config.from_object(config_source)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    init_csrf(app)
    init_database(app)

    from .blueprints.main.routes import bp as main_bp
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.api.routes import bp as api_bp
    from .blueprints.profile.routes import bp as profile_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(profile_bp)

    @app.context_processor
    def inject_app_config():
        return {"app_name": "Budget Tracker"}

    return app
