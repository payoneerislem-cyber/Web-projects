from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Cart, Coupon, CouponUsage, Order, User
from app.models.mixins import utcnow
from app.services import coupon_service
from app.services.coupon_service import CouponError
from seed import seed_database
from tests.flow import AURORA, CASE, CUSTOMER, add_to_cart, checkout_data, login, place_order, product


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def coupon(code):
    return Coupon.query.filter_by(code=code).one()


def customer():
    return User.query.filter_by(email=CUSTOMER[0]).one()


def apply(client, code):
    return client.post("/api/cart/coupon", json={"code": code})


def cart(client):
    return client.get("/api/cart").get_json()["cart"]


def test_discount_math(app):
    pct = Coupon(code="A", discount_type="percentage", discount_value=10)
    assert coupon_service.discount_amount(pct, 14900) == 1490
    assert coupon_service.discount_amount(pct, 1005) == 101  # 100.5 rounds half up
    fixed = Coupon(code="B", discount_type="fixed", discount_value=500)
    assert coupon_service.discount_amount(fixed, 9000) == 500
    assert coupon_service.discount_amount(fixed, 300) == 300  # never more than the goods cost
    capped = Coupon(code="C", discount_type="percentage", discount_value=25, maximum_discount=5000)
    assert coupon_service.discount_amount(capped, 40000) == 5000
    assert coupon_service.discount_amount(capped, 10000) == 2500


@pytest.mark.parametrize("code, subtotal, message", [
    ("", 5000, "Enter a coupon code"), ("NOPE", 5000, "isn't valid"), ("expired20", 5000, "expired"),
    ("SAVE5", 1000, "minimum order of $25.00"), ("BIG25", 5000, "minimum order of $200.00"),
])
def test_validation_rejections(app, seeded, code, subtotal, message):
    with pytest.raises(CouponError, match=message):
        coupon_service.validate(code, subtotal)


def test_other_rejections(app, seeded):
    c = coupon("SAVE5")
    c.is_active = False
    db.session.commit()
    with pytest.raises(CouponError, match="isn't valid"):
        coupon_service.validate("SAVE5", 5000)
    c.is_active, c.start_date = True, utcnow() + timedelta(days=1)
    db.session.commit()
    with pytest.raises(CouponError, match="isn't active yet"):
        coupon_service.validate("SAVE5", 5000)
    c.start_date, c.usage_limit, c.used_count = None, 1, 1
    db.session.commit()
    with pytest.raises(CouponError, match="usage limit"):
        coupon_service.validate("SAVE5", 5000)


def test_per_user_limit(app, seeded):
    user, welcome = customer(), coupon("WELCOME10")
    assert coupon_service.validate("WELCOME10", 5000, user).id == welcome.id
    db.session.add(CouponUsage(coupon_id=welcome.id, user_id=user.id))
    db.session.commit()
    with pytest.raises(CouponError, match="already used"):
        coupon_service.validate("WELCOME10", 5000, user)


def test_apply_and_remove_coupon(client, seeded):
    add_to_cart(client, AURORA, 1)
    r = apply(client, " welcome10 ")
    data = r.get_json()["cart"]
    assert r.status_code == 200 and data["coupon"]["code"] == "WELCOME10"
    assert (data["subtotal"], data["discount"], data["total"]) == (14900, 1490, 13410)
    assert data["formatted"]["discount"] == "-$14.90"
    page = client.get("/cart")
    for text in (b"WELCOME10", b"-$14.90", b"$134.10", b"data-coupon-remove", b"Coupon WELCOME10 applied"):
        assert text in page.data, text
    r = client.delete("/api/cart/coupon")
    after = r.get_json()["cart"]
    assert r.status_code == 200 and after["coupon"] is None and after["discount"] == 0 and after["total"] == 14900


def test_apply_errors(client, seeded):
    r = apply(client, "SAVE5")
    assert r.status_code == 400 and "Add something" in r.get_json()["error"]
    add_to_cart(client, CASE, 1)
    for code, text in (("BIG25", "minimum order of $200.00"), ("NOPE", "isn't valid"), ("", "Enter a coupon code"), (123, "isn't valid")):
        r = apply(client, code)
        assert r.status_code == 400 and text in r.get_json()["error"] and r.get_json()["ok"] is False
    assert client.post("/api/cart/coupon", data="x", content_type="text/plain").status_code == 400
    assert cart(client)["coupon"] is None


def test_percentage_cap_and_shipping_threshold(client, seeded):
    add_to_cart(client, AURORA, 2)  # $298.00
    assert apply(client, "BIG25").get_json()["cart"]["discount"] == 5000  # 25% = 7450, capped at $50
    client.delete("/api/cart")
    add_to_cart(client, CASE, 2)  # $50.00 -> free shipping...
    data = apply(client, "SAVE5").get_json()["cart"]  # ...until $5 off drops it below the threshold
    assert data["subtotal"] == 5000 and data["shipping"] == 599 and data["total"] == 4500 + 599


def test_discount_never_exceeds_subtotal(client, seeded):
    db.session.add(Coupon(code="HUGE", discount_type="fixed", discount_value=100000, per_user_limit=5))
    db.session.commit()
    add_to_cart(client, CASE, 1)
    data = apply(client, "HUGE").get_json()["cart"]
    assert data["discount"] == 2500 and data["total"] == 0


def test_coupon_is_dropped_when_it_expires(client, seeded):
    add_to_cart(client, CASE, 2)
    apply(client, "SAVE5")
    coupon("SAVE5").expiry_date = utcnow() - timedelta(days=1)
    db.session.commit()
    assert cart(client)["coupon"] is None
    assert b"was removed" in client.get("/cart").data
    assert Cart.query.one().coupon_code is None


def test_coupon_is_dropped_when_cart_falls_below_minimum(client, seeded):
    item_id = add_to_cart(client, AURORA, 2).get_json()["cart"]["items"][0]["id"]
    apply(client, "BIG25")
    r = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 1})  # $149 < $200 minimum
    assert r.get_json()["cart"]["coupon"] is None and r.get_json()["cart"]["discount"] == 0
    assert b"minimum order" in client.get("/cart").data
    assert Cart.query.one().coupon_code is None


def test_guest_coupon_survives_login(client, seeded):
    add_to_cart(client, AURORA, 1)
    apply(client, "SAVE5")
    login(client)
    assert cart(client)["coupon"]["code"] == "SAVE5"


def test_checkout_with_coupon(client, seeded):
    order = place_order(client, ((AURORA, 2),), coupon="welcome10")
    assert order.coupon_code == "WELCOME10"
    assert (order.subtotal, order.discount, order.total) == (29800, 2980, 26820)
    assert coupon("WELCOME10").used_count == 1
    usage = CouponUsage.query.one()
    assert usage.order_id == order.id and usage.user_id == order.user_id
    assert Cart.query.filter_by(user_id=order.user_id).one().coupon_code is None
    assert b"Discount (WELCOME10)" in client.get(f"/checkout/confirmation/{order.order_number}").data


def test_checkout_page_shows_the_discount(client, seeded):
    login(client)
    add_to_cart(client, AURORA, 1)
    apply(client, "WELCOME10")
    page = client.get("/checkout")
    assert b"Discount (WELCOME10)" in page.data and b"$134.10" in page.data


def test_one_use_per_customer(client, seeded):
    place_order(client, coupon="WELCOME10")
    add_to_cart(client, AURORA, 1)
    r = apply(client, "WELCOME10")
    assert r.status_code == 400 and "already used" in r.get_json()["error"]


def test_coupon_that_became_invalid_blocks_checkout(client, seeded):
    login(client)
    add_to_cart(client, CASE, 2)
    apply(client, "SAVE5")
    coupon("SAVE5").expiry_date = utcnow() - timedelta(days=1)
    db.session.commit()
    r = client.post("/checkout", data=checkout_data())
    assert r.status_code == 302 and r.headers["Location"].endswith("/cart")
    assert Order.query.count() == 0


def test_usage_limit_cannot_be_exceeded_by_a_race(client, seeded, monkeypatch):
    login(client)
    add_to_cart(client, AURORA, 2)
    apply(client, "BIG25")
    big = coupon("BIG25")
    big.usage_limit, big.used_count = 1, 1  # someone else just took the last use
    db.session.commit()
    monkeypatch.setattr(coupon_service, "validate", lambda code, subtotal, user=None: coupon("BIG25"))
    stock = product(AURORA).stock_quantity
    r = client.post("/checkout", data=checkout_data())
    assert r.status_code == 302 and r.headers["Location"].endswith("/cart")
    assert Order.query.count() == 0 and product(AURORA).stock_quantity == stock
    assert coupon("BIG25").used_count == 1


def test_cancelling_gives_the_coupon_back(client, seeded):
    order = place_order(client, coupon="WELCOME10")
    client.post(f"/account/orders/{order.order_number}/cancel")
    assert coupon("WELCOME10").used_count == 0 and CouponUsage.query.count() == 0
    add_to_cart(client, AURORA, 1)
    assert apply(client, "WELCOME10").status_code == 200
