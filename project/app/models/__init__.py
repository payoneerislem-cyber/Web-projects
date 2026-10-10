"""Import every model so SQLAlchemy and Alembic register all tables."""
from app.models.cart import Cart, CartItem, Wishlist, WishlistItem
from app.models.catalog import Category, Product, ProductImage
from app.models.coupon import Coupon, CouponUsage, DiscountType
from app.models.misc import NewsletterSubscriber, Notification, Setting
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.models.review import Review, ReviewStatus
from app.models.user import Address, Role, User

__all__ = [
    "Address", "Cart", "CartItem", "Category", "Coupon", "CouponUsage",
    "DiscountType", "NewsletterSubscriber", "Notification", "Order", "OrderItem",
    "OrderStatus", "PaymentStatus", "Product", "ProductImage", "Review",
    "ReviewStatus", "Role", "Setting", "User", "Wishlist", "WishlistItem",
]
