"""Wishlist business logic. Wishlists belong to logged-in users."""
from flask import current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Product, Wishlist, WishlistItem
from app.services import cart_service
from app.utils.validators import parse_int


class WishlistError(Exception):
    """A problem the visitor can understand (shown as a toast)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _valid_product_id(value) -> int:
    product_id = parse_int(value)
    if product_id is None:
        raise WishlistError("Invalid product.")
    return product_id


def get_wishlist(user, create: bool = False):
    wishlist = Wishlist.query.filter_by(user_id=user.id).first()
    if wishlist is None and create:
        wishlist = Wishlist(user_id=user.id)
        db.session.add(wishlist)
        try:
            db.session.flush()
        except IntegrityError:  # created concurrently by another request
            db.session.rollback()
            wishlist = Wishlist.query.filter_by(user_id=user.id).first()
    return wishlist


def _entry(user, product_id):
    return (WishlistItem.query.join(Wishlist, Wishlist.id == WishlistItem.wishlist_id)
            .filter(Wishlist.user_id == user.id, WishlistItem.product_id == product_id).first())


def product_ids(user) -> set:
    """Ids of wishlisted products that are still on sale (one query)."""
    rows = (db.session.query(WishlistItem.product_id)
            .join(Wishlist, Wishlist.id == WishlistItem.wishlist_id)
            .join(Product, Product.id == WishlistItem.product_id)
            .filter(Wishlist.user_id == user.id, Product.is_active.is_(True),
                    Product.deleted_at.is_(None))
            .all())
    return {row[0] for row in rows}


def list_products(user):
    """Wishlisted products that are still on sale, newest first (images eager-loaded)."""
    return (Product.visible_query().options(selectinload(Product.images))
            .join(WishlistItem, WishlistItem.product_id == Product.id)
            .join(Wishlist, Wishlist.id == WishlistItem.wishlist_id)
            .filter(Wishlist.user_id == user.id)
            .order_by(WishlistItem.added_at.desc(), WishlistItem.id.desc()).all())


def add(user, product_id) -> bool:
    """Add a product. Returns False if it was already there (never duplicates)."""
    product_id = _valid_product_id(product_id)
    product = db.session.get(Product, product_id)
    if product is None or not product.is_active or product.deleted_at is not None:
        raise WishlistError("This product is no longer available.", 404)
    wishlist = get_wishlist(user, create=True)
    if any(item.product_id == product_id for item in wishlist.items):
        return False
    limit = current_app.config["MAX_WISHLIST_ITEMS"]
    if len(wishlist.items) >= limit:
        raise WishlistError(f"Your wishlist is full ({limit} items). Remove something first.", 409)
    wishlist.items.append(WishlistItem(product_id=product_id))
    try:
        db.session.commit()
    except IntegrityError:  # same product added twice at once
        db.session.rollback()
        return False
    return True


def remove(user, product_id) -> bool:
    """Remove a product. Returns False if it wasn't there (idempotent)."""
    entry = _entry(user, _valid_product_id(product_id))
    if entry is None:
        return False
    db.session.delete(entry)
    db.session.commit()
    return True


def toggle(user, product_id) -> bool:
    """Flip membership. Returns True if the product is in the wishlist afterwards."""
    if remove(user, product_id):
        return False
    add(user, product_id)
    return True


def move_to_cart(user, product_id) -> Product:
    """Put one unit in the cart, then drop it from the wishlist.

    If the cart refuses (out of stock, limit reached) the item stays wishlisted.
    """
    product_id = _valid_product_id(product_id)
    if _entry(user, product_id) is None:
        raise WishlistError("That product isn't in your wishlist.", 404)
    product = cart_service.add_item(product_id, 1)  # CartError propagates to the API layer
    remove(user, product_id)
    return product
