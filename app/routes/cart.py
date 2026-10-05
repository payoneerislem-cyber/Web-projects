"""Cart page. The JSON operations live in app/routes/api.py."""
from flask import Blueprint, flash, render_template

from app.services import cart_service

bp = Blueprint("cart", __name__)


@bp.get("/cart")
def view():
    cart, notices = cart_service.reconcile(cart_service.get_cart())
    for notice in notices:
        flash(notice, "warning")
    return render_template("cart/cart.html", cart=cart_service.serialize(cart))
