"""Template globals and context processors shared by every page."""
import os

from flask import current_app, g, session, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.routing import BuildError

from app.extensions import db


def safe_url(endpoint: str, fallback: str = "#", **values) -> str:
    """url_for() that falls back to a plain path while a page isn't built yet.

    Lets the layout link to pages from later phases and upgrade to real
    endpoints automatically once they exist.
    """
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return fallback


def in_wishlist(product_id) -> bool:
    """True if the logged-in visitor has wishlisted this product (used by product cards)."""
    return product_id in _nav_data()["wishlist_ids"]


def asset(filename: str) -> str:
    """Static URL with a ?v=<mtime> cache-buster so edits show up immediately."""
    try:
        version = int(os.path.getmtime(os.path.join(current_app.static_folder, filename)))
    except OSError:
        version = 0
    return url_for("static", filename=filename, v=version)


def _nav_data() -> dict:
    """Header data (categories + badge counts). Cached per request and fail-safe,
    because error pages also render the header and must never crash."""
    if hasattr(g, "_nav_data"):
        return g._nav_data
    data = {"nav_categories": [], "cart_count": 0, "wishlist_count": 0, "wishlist_ids": set()}
    try:
        from app.models import Cart, CartItem, Category
        from app.services.cart_service import CART_TOKEN_KEY

        data["nav_categories"] = (
            Category.query.filter_by(is_active=True).order_by(Category.name).limit(10).all()
        )

        owner = None  # whose cart to count: the user's, or the guest's (token in session)
        if current_user.is_authenticated:
            owner = Cart.user_id == current_user.id
        elif session.get(CART_TOKEN_KEY):
            owner = Cart.session_token == session[CART_TOKEN_KEY]
        if owner is not None:
            data["cart_count"] = (
                db.session.query(func.coalesce(func.sum(CartItem.quantity), 0))
                .join(Cart, Cart.id == CartItem.cart_id)
                .filter(owner)
                .scalar()
            ) or 0

        if current_user.is_authenticated:
            from app.services import wishlist_service

            data["wishlist_ids"] = wishlist_service.product_ids(current_user)
            data["wishlist_count"] = len(data["wishlist_ids"])
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not load header data")
    g._nav_data = data
    return data


def register_context(app) -> None:
    from datetime import datetime, timezone

    app.jinja_env.globals.update(safe_url=safe_url, asset=asset, in_wishlist=in_wishlist)

    @app.context_processor
    def inject_globals():
        return {
            "STORE_NAME": app.config["STORE_NAME"],
            "CURRENCY": app.config["CURRENCY_SYMBOL"],
            "ANNOUNCEMENT": app.config.get("ANNOUNCEMENT_TEXT", ""),
            "current_year": datetime.now(timezone.utc).year,
            **_nav_data(),
        }
