"""Cart business logic: guest + user carts, validation, reconciliation, totals."""
import secrets
from datetime import timedelta

from flask import current_app, session, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Cart, CartItem, Product
from app.models.mixins import utcnow
from app.services import pricing_service
from app.utils.money import format_money

CART_TOKEN_KEY = "cart_token"  # lives in the signed session cookie
GUEST_CART_TTL_DAYS = 30


class CartError(Exception):
    """A problem the visitor can understand (shown as a toast)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- helpers
def _purchasable(product) -> bool:
    return product is not None and product.is_active and product.deleted_at is None


def _max_for(product) -> int:
    """Most units of this product one cart line may hold."""
    return max(min(product.stock_quantity, current_app.config["MAX_QTY_PER_ITEM"]), 0)


def _stock_bound(product) -> bool:
    return product.stock_quantity <= current_app.config["MAX_QTY_PER_ITEM"]


def _to_int(value, message: str) -> int:
    if isinstance(value, bool):
        raise CartError(message)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value.strip())
    raise CartError(message)


def _valid_quantity(value) -> int:
    quantity = _to_int(value, "Please enter a valid quantity.")
    maximum = current_app.config["MAX_QTY_PER_ITEM"]
    if quantity < 1:
        raise CartError("Quantity must be at least 1.")
    if quantity > maximum:
        raise CartError(f"You can buy at most {maximum} of one item per order.")
    return quantity


def _touch(cart: Cart) -> None:
    cart.updated_at = utcnow()


# ---------------------------------------------------------------- carts
def _base_query():
    return Cart.query.options(
        selectinload(Cart.items).joinedload(CartItem.product).selectinload(Product.images))


def get_cart(create: bool = False):
    """The current visitor's cart (user cart if logged in, else the guest cart)."""
    if current_user.is_authenticated:
        cart = _base_query().filter(Cart.user_id == current_user.id).first()
        if cart is None and create:
            cart = Cart(user_id=current_user.id)
            db.session.add(cart)
            try:
                db.session.flush()
            except IntegrityError:  # created concurrently by another request
                db.session.rollback()
                cart = _base_query().filter(Cart.user_id == current_user.id).first()
        return cart

    token = session.get(CART_TOKEN_KEY)
    cart = _base_query().filter(Cart.session_token == token).first() if token else None
    if cart is None and create:
        purge_stale_guest_carts()
        token = secrets.token_urlsafe(32)
        cart = Cart(session_token=token)
        db.session.add(cart)
        db.session.flush()
        session[CART_TOKEN_KEY] = token
        session.permanent = True  # guests keep their cart across browser restarts
    return cart


def purge_stale_guest_carts(days: int = GUEST_CART_TTL_DAYS) -> int:
    """Delete abandoned guest carts (their items go with them via ON DELETE CASCADE)."""
    cutoff = utcnow() - timedelta(days=days)
    deleted = (Cart.query.filter(Cart.user_id.is_(None), Cart.updated_at < cutoff)
               .delete(synchronize_session=False))
    db.session.commit()
    return deleted


def merge_guest_cart(user) -> None:
    """After login/registration: fold the guest cart into the user's cart."""
    token = session.pop(CART_TOKEN_KEY, None)
    if not token:
        return
    guest = Cart.query.filter_by(session_token=token).first()
    if guest is None or guest.user_id is not None:
        return
    mine = Cart.query.filter_by(user_id=user.id).first()
    if mine is None:  # nothing to merge into: the guest cart simply becomes theirs
        guest.user_id = user.id
        guest.session_token = None
        db.session.commit()
        return

    existing = {item.product_id: item for item in mine.items}
    for guest_item in list(guest.items):
        product = guest_item.product
        if not _purchasable(product) or _max_for(product) < 1:
            continue
        limit = _max_for(product)
        if guest_item.product_id in existing:
            line = existing[guest_item.product_id]
            line.quantity = min(line.quantity + guest_item.quantity, limit)
        else:
            db.session.add(CartItem(cart_id=mine.id, product_id=guest_item.product_id,
                                    quantity=min(guest_item.quantity, limit)))
    if not mine.coupon_code and guest.coupon_code:
        mine.coupon_code = guest.coupon_code
    _touch(mine)
    db.session.delete(guest)
    db.session.commit()


# ---------------------------------------------------------------- operations
def add_item(product_id, quantity) -> Product:
    product_id = _to_int(product_id, "Invalid product.")
    quantity = _valid_quantity(quantity)
    product = db.session.get(Product, product_id)
    if not _purchasable(product):
        raise CartError("This product is no longer available.", 404)
    if product.stock_quantity <= 0:
        raise CartError(f"“{product.name}” is out of stock.", 409)

    cart = get_cart(create=True)
    line = next((i for i in cart.items if i.product_id == product.id), None)
    current = line.quantity if line else 0
    limit = _max_for(product)
    if current + quantity > limit:
        remaining = limit - current
        reason = "stock limit" if _stock_bound(product) else "per-order limit"
        if remaining <= 0:
            raise CartError(f"You already have the maximum ({limit}) of this item in your cart.", 409)
        raise CartError(f"Only {remaining} more can be added ({reason}).", 409)

    if line is not None:
        line.quantity += quantity
    else:
        cart.items.append(CartItem(product_id=product.id, quantity=quantity))
    _touch(cart)
    try:
        db.session.commit()
    except IntegrityError:  # same product added twice at once: retry as an update
        db.session.rollback()
        cart = get_cart(create=True)
        line = next((i for i in cart.items if i.product_id == product.id), None)
        if line is None:
            raise CartError("Couldn't add that item. Please try again.", 409) from None
        line.quantity = min(line.quantity + quantity, limit)
        _touch(cart)
        db.session.commit()
    return product


def _owned_item(cart, item_id) -> CartItem:
    item_id = _to_int(item_id, "Item not found.")
    item = next((i for i in cart.items if i.id == item_id), None) if cart else None
    if item is None:
        raise CartError("That item isn't in your cart.", 404)
    return item


def set_quantity(item_id, quantity) -> None:
    cart = get_cart()
    item = _owned_item(cart, item_id)
    quantity = _valid_quantity(quantity)
    product = item.product
    if not _purchasable(product) or product.stock_quantity <= 0:
        raise CartError("This product is no longer available.", 409)
    limit = _max_for(product)
    if quantity > limit:
        raise CartError(f"Only {limit} available.", 409)
    item.quantity = quantity
    _touch(cart)
    db.session.commit()


def remove_item(item_id) -> None:
    cart = get_cart()
    item = _owned_item(cart, item_id)
    db.session.delete(item)
    _touch(cart)
    db.session.commit()


def clear_cart() -> None:
    cart = get_cart()
    if cart is None:
        return
    for item in list(cart.items):
        db.session.delete(item)
    cart.coupon_code = None
    _touch(cart)
    db.session.commit()


def reconcile(cart):
    """Drop unavailable items and clamp quantities to current stock.

    Returns (cart, notices); notices are messages to show the visitor.
    """
    if cart is None or not cart.items:
        return cart, []
    notices, changed = [], False
    for item in list(cart.items):
        product = item.product
        name = product.name if product is not None else "An item"
        if not _purchasable(product) or product.stock_quantity <= 0:
            db.session.delete(item)
            notices.append(f"“{name}” is no longer available and was removed from your cart.")
            changed = True
        elif item.quantity > _max_for(product):
            item.quantity = _max_for(product)
            notices.append(f"Only {item.quantity} of “{name}” available, so we updated your quantity.")
            changed = True
    if changed:
        _touch(cart)
        db.session.commit()
        cart = get_cart()
    return cart, notices


# ---------------------------------------------------------------- output
def serialize(cart) -> dict:
    """Plain dict used by both the cart page and the JSON API."""
    symbol = current_app.config["CURRENCY_SYMBOL"]

    def money(cents):
        return format_money(cents, symbol)

    items = []
    for line in (cart.items if cart is not None else []):
        product = line.product
        total = product.price * line.quantity
        items.append({
            "id": line.id,
            "product_id": product.id,
            "name": product.name,
            "brand": product.brand,
            "url": url_for("shop.product", slug=product.slug),
            "image": product.image_url,
            "quantity": line.quantity,
            "max_quantity": _max_for(product),
            "unit_price": product.price,
            "unit_price_formatted": money(product.price),
            "line_total": total,
            "line_total_formatted": money(total),
            "stock_note": (f"Only {product.stock_quantity} left"
                           if product.stock_status == "low_stock" else ""),
        })

    subtotal = sum(i["line_total"] for i in items)
    totals = pricing_service.calculate(subtotal)
    return {
        "count": sum(i["quantity"] for i in items),
        "items": items,
        "subtotal": totals["subtotal"],
        "discount": totals["discount"],
        "shipping": totals["shipping"],
        "tax": totals["tax"],
        "total": totals["total"],
        "free_shipping_threshold": totals["free_shipping_threshold"],
        "free_shipping_remaining": totals["free_shipping_remaining"],
        "free_shipping_remaining_formatted": money(totals["free_shipping_remaining"]),
        "formatted": {
            "subtotal": money(totals["subtotal"]),
            "discount": money(-totals["discount"]) if totals["discount"] else money(0),
            "shipping": "Free" if totals["shipping"] == 0 else money(totals["shipping"]),
            "tax": money(totals["tax"]),
            "total": money(totals["total"]),
        },
    }
