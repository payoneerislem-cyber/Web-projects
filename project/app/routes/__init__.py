"""Blueprint registration."""
from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.account import bp as account_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.api import bp as api_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.cart import bp as cart_bp
    from app.routes.main import bp as main_bp
    from app.routes.shop import bp as shop_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
