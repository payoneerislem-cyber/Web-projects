"""JSON endpoints used by the front-end (more are added in later phases)."""
from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required

from app.extensions import db, limiter
from app.services import cart_service, catalog_service, wishlist_service
from app.services.cart_service import CartError
from app.services.wishlist_service import WishlistError
from app.utils.money import format_money

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/search/suggest")
@limiter.limit("60 per minute")
def search_suggest():
    q = " ".join((request.args.get("q") or "").split())[:100]
    if len(q) < 2:
        return jsonify({"ok": True, "products": [], "categories": []})
    products, categories = catalog_service.suggest(q, limit=6)
    symbol = current_app.config["CURRENCY_SYMBOL"]
    return jsonify({
        "ok": True,
        "products": [{
            "name": p.name,
            "url": url_for("shop.product", slug=p.slug),
            "price": format_money(p.price, symbol),
            "image": p.image_url,
            "category": p.category.name,
        } for p in products],
        "categories": [{"name": c.name, "url": url_for("shop.category", slug=c.slug)}
                       for c in categories],
    })


# ---------------------------------------------------------------- cart
def _body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise CartError("Invalid request.")
    return data


@bp.errorhandler(CartError)
def cart_error(exc):
    """Business-rule failures: tell the visitor why and send the current cart so
    the page can resync."""
    db.session.rollback()
    return jsonify({"ok": False, "error": str(exc),
                    "cart": cart_service.serialize(cart_service.get_cart())}), exc.status


@bp.get("/cart")
@limiter.limit("120 per minute")
def cart_get():
    cart, notices = cart_service.reconcile(cart_service.get_cart())
    return jsonify({"ok": True, "cart": cart_service.serialize(cart), "notices": notices})


@bp.post("/cart/add")
@limiter.limit("120 per minute")
def cart_add():
    body = _body()
    product = cart_service.add_item(body.get("product_id"), body.get("quantity", 1))
    return jsonify({"ok": True, "message": f"Added \u201c{product.name}\u201d to your cart.",
                    "cart": cart_service.serialize(cart_service.get_cart())})


@bp.patch("/cart/items/<int:item_id>")
@limiter.limit("120 per minute")
def cart_update(item_id):
    cart_service.set_quantity(item_id, _body().get("quantity"))
    return jsonify({"ok": True, "cart": cart_service.serialize(cart_service.get_cart())})


@bp.delete("/cart/items/<int:item_id>")
@limiter.limit("120 per minute")
def cart_remove(item_id):
    cart_service.remove_item(item_id)
    return jsonify({"ok": True, "cart": cart_service.serialize(cart_service.get_cart())})


@bp.delete("/cart")
@limiter.limit("60 per minute")
def cart_clear():
    cart_service.clear_cart()
    return jsonify({"ok": True, "cart": cart_service.serialize(cart_service.get_cart())})


# ---------------------------------------------------------------- wishlist (login required)
def _wishlist_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise WishlistError("Invalid request.")
    return data


@bp.errorhandler(WishlistError)
def wishlist_error(exc):
    db.session.rollback()
    return jsonify({"ok": False, "error": str(exc)}), exc.status


@bp.post("/wishlist/toggle")
@limiter.limit("120 per minute")
@login_required
def wishlist_toggle():
    in_list = wishlist_service.toggle(current_user, _wishlist_body().get("product_id"))
    return jsonify({
        "ok": True, "in_wishlist": in_list,
        "count": len(wishlist_service.product_ids(current_user)),
        "message": "Added to your wishlist." if in_list else "Removed from your wishlist.",
    })


@bp.delete("/wishlist/<int:product_id>")
@limiter.limit("120 per minute")
@login_required
def wishlist_remove(product_id):
    wishlist_service.remove(current_user, product_id)
    return jsonify({"ok": True, "count": len(wishlist_service.product_ids(current_user))})


@bp.post("/wishlist/<int:product_id>/move-to-cart")
@limiter.limit("120 per minute")
@login_required
def wishlist_move_to_cart(product_id):
    product = wishlist_service.move_to_cart(current_user, product_id)
    return jsonify({
        "ok": True,
        "message": f"Moved \u201c{product.name}\u201d to your cart.",
        "count": len(wishlist_service.product_ids(current_user)),
        "cart_count": cart_service.serialize(cart_service.get_cart())["count"],
    })
