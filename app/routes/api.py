"""JSON endpoints used by the front-end (more are added in later phases)."""
from flask import Blueprint, current_app, jsonify, request, url_for

from app.extensions import db, limiter
from app.services import cart_service, catalog_service
from app.services.cart_service import CartError
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
