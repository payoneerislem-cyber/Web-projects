import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db, load_user
from app.models import (
    Cart, CartItem, Category, Coupon, Order, OrderItem, OrderStatus, Product,
    Review, User, Wishlist, WishlistItem,
)
from app.models.mixins import utcnow
from app.utils.money import format_money, to_cents
from app.utils.slugs import unique_slug


def make_user(email="a@example.com", **kw):
    user = User(email=email, name=kw.pop("name", "Ada Lovelace"), **kw)
    user.set_password("Secret123!")
    db.session.add(user)
    db.session.commit()
    return user


def make_category(name="Audio"):
    cat = Category(name=name, slug=name.lower())
    db.session.add(cat)
    db.session.commit()
    return cat


def make_product(cat, **kw):
    data = dict(name="Headphones", slug="headphones", sku="SKU-1", price=9900,
                stock_quantity=10, category_id=cat.id)
    data.update(kw)
    product = Product(**data)
    db.session.add(product)
    db.session.commit()
    return product


def test_password_is_hashed(app):
    user = make_user()
    assert user.password_hash != "Secret123!"
    assert user.check_password("Secret123!")
    assert not user.check_password("wrong")
    assert user.role == "customer" and not user.is_admin


def test_email_unique(app):
    make_user()
    db.session.add(User(email="a@example.com", name="Dup", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_loader(app):
    user = make_user()
    assert load_user(str(user.id)).id == user.id
    assert load_user("9999") is None
    assert load_user("abc") is None
    user.is_active = False
    db.session.commit()
    assert load_user(str(user.id)) is None


def test_product_discount_and_stock_status(app):
    cat = make_category()
    p = make_product(cat, price=7500, compare_at_price=10000, stock_quantity=3)
    assert p.discount_percent == 25
    assert p.stock_status == "low_stock"
    p.stock_quantity = 0
    assert p.stock_status == "out_of_stock" and not p.is_available
    p.stock_quantity = 50
    assert p.stock_status == "in_stock" and p.is_available


def test_negative_stock_rejected(app):
    cat = make_category()
    db.session.add(Product(name="X", slug="x", sku="X", price=100, stock_quantity=-1,
                           category_id=cat.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_soft_deleted_product_is_hidden(app):
    cat = make_category()
    p = make_product(cat)
    assert Product.visible_query().count() == 1
    p.deleted_at = utcnow()
    db.session.commit()
    assert Product.visible_query().count() == 0


def test_category_with_products_cannot_be_deleted(app):
    cat = make_category()
    make_product(cat)
    db.session.delete(cat)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_order_item_survives_product_deletion(app):
    user = make_user()
    p = make_product(make_category())
    order = Order(order_number="LM-0001", user_id=user.id, subtotal=9900, total=9900,
                  shipping_address={"city": "Cairo"})
    order.items.append(OrderItem(product_id=p.id, product_name_snapshot=p.name,
                                 price_snapshot=p.price, quantity=1, subtotal=p.price))
    db.session.add(order)
    db.session.commit()

    db.session.delete(p)
    db.session.commit()

    item = db.session.get(OrderItem, order.items[0].id)
    assert item.product_id is None
    assert item.product_name_snapshot == "Headphones"
    assert item.price_snapshot == 9900


def test_order_status_transitions(app):
    order = Order(order_number="LM-0002", shipping_address={}, status=OrderStatus.PENDING)
    assert order.can_transition_to(OrderStatus.CONFIRMED)
    assert not order.can_transition_to(OrderStatus.DELIVERED)
    order.status = OrderStatus.CANCELLED
    assert not order.can_transition_to(OrderStatus.PENDING)


def test_cart_item_unique_and_cascade(app):
    user = make_user()
    p = make_product(make_category())
    cart = Cart(user_id=user.id)
    cart.items.append(CartItem(product_id=p.id, quantity=2))
    db.session.add(cart)
    db.session.commit()

    db.session.add(CartItem(cart_id=cart.id, product_id=p.id, quantity=1))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    db.session.delete(cart)
    db.session.commit()
    assert CartItem.query.count() == 0


def test_cart_requires_owner(app):
    db.session.add(Cart())
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_wishlist_no_duplicates(app):
    user = make_user()
    p = make_product(make_category())
    wl = Wishlist(user_id=user.id)
    wl.items.append(WishlistItem(product_id=p.id))
    db.session.add(wl)
    db.session.commit()
    db.session.add(WishlistItem(wishlist_id=wl.id, product_id=p.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_review_rating_range_and_unique(app):
    user = make_user()
    p = make_product(make_category())
    db.session.add(Review(user_id=user.id, product_id=p.id, rating=6))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    db.session.add(Review(user_id=user.id, product_id=p.id, rating=5))
    db.session.commit()
    db.session.add(Review(user_id=user.id, product_id=p.id, rating=4))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_coupon_defaults(app):
    c = Coupon(code="SAVE10", discount_type="percentage", discount_value=10)
    db.session.add(c)
    db.session.commit()
    assert c.used_count == 0 and c.is_active and not c.is_expired


def test_money_helpers():
    assert to_cents("19.99") == 1999
    assert to_cents(5) == 500
    assert to_cents("0.005") == 1
    with pytest.raises(ValueError):
        to_cents("abc")
    assert format_money(123456) == "$1,234.56"
    assert format_money(5) == "$0.05"


def test_unique_slug(app):
    cat = make_category("Audio")
    assert unique_slug(Category, "Audio") == "audio-2"
    assert unique_slug(Category, "Audio", exclude_id=cat.id) == "audio"
    assert unique_slug(Category, "Smart Watches!") == "smart-watches"
