from app.extensions import db
from app.models.mixins import utcnow


class Cart(db.Model):
    """One cart per logged-in user, or per guest identified by a signed token."""

    __tablename__ = "carts"
    __table_args__ = (
        db.CheckConstraint(
            "user_id IS NOT NULL OR session_token IS NOT NULL", name="owner_present"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    session_token = db.Column(db.String(64), unique=True, index=True)
    coupon_code = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = db.relationship("User", back_populates="cart")
    items = db.relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan",
        passive_deletes=True, order_by="CartItem.id",
    )


class CartItem(db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (
        db.UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
        db.CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(
        db.Integer, db.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    added_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product")


class Wishlist(db.Model):
    __tablename__ = "wishlists"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="wishlist")
    items = db.relationship(
        "WishlistItem", back_populates="wishlist", cascade="all, delete-orphan",
        passive_deletes=True, order_by="desc(WishlistItem.added_at)",
    )


class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    __table_args__ = (
        db.UniqueConstraint("wishlist_id", "product_id", name="uq_wishlist_items_wishlist_product"),
    )

    id = db.Column(db.Integer, primary_key=True)
    wishlist_id = db.Column(
        db.Integer, db.ForeignKey("wishlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    added_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    wishlist = db.relationship("Wishlist", back_populates="items")
    product = db.relationship("Product")
