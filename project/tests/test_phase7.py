import re
from datetime import timedelta

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import Cart, CartItem, Product, User
from app.models.mixins import utcnow
from app.services import cart_service, pricing_service
from seed import seed_database

CUSTOMER = ("customer@example.com", "Customer12345")


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def pid(slug):
    return Product.query.filter_by(slug=slug).one().id


def add(client, slug, quantity=1):
    return client.post("/api/cart/add", json={"product_id": pid(slug), "quantity": quantity})


def cart_json(client):
    return client.get("/api/cart").get_json()["cart"]


def login(client, email=CUSTOMER[0], password=CUSTOMER[1]):
    return client.post("/login", data={"email": email, "password": password})


AURORA, BASSLINE, CASE = "aurora-wireless-headphones", "bassline-portable-speaker", "phone-case-shield"


# ------------------------------------------------------------ pricing
def test_pricing_rules(app):
    with app.test_request_context():
        assert pricing_service.calculate(0)["shipping"] == 0
        assert pricing_service.calculate(4999)["shipping"] == 599
        assert pricing_service.calculate(5000)["shipping"] == 0
        # the discount counts toward the free-shipping threshold
        assert pricing_service.calculate(5500, discount=1000)["shipping"] == 599
        assert pricing_service.calculate(4999)["free_shipping_remaining"] == 1

        app.config["TAX_RATE"] = "0.0825"
        t = pricing_service.calculate(10000)
        assert t["tax"] == 825 and t["total"] == 10825
        t = pricing_service.calculate(10000, discount=2000)  # tax on the discounted amount
        assert t["tax"] == 660 and t["total"] == 8660
        app.config["TAX_RATE"] = "junk"
        assert pricing_service.calculate(10000)["tax"] == 0


# ------------------------------------------------------------ guest cart API
def test_guest_add_and_totals(client, seeded):
    r = add(client, AURORA, 2)
    data = r.get_json()
    assert r.status_code == 200 and data["ok"] is True and "Aurora Wireless Headphones" in data["message"]
    cart = data["cart"]
    assert cart["count"] == 2 and len(cart["items"]) == 1
    assert cart["subtotal"] == 29800 and cart["shipping"] == 0 and cart["tax"] == 0
    assert cart["total"] == 29800 and cart["formatted"]["total"] == "$298.00"
    assert cart["formatted"]["shipping"] == "Free"
    assert cart_json(client)["count"] == 2  # the session keeps the guest cart


def test_adding_same_product_merges_lines(client, seeded):
    add(client, AURORA, 1)
    add(client, AURORA, 2)
    cart = cart_json(client)
    assert len(cart["items"]) == 1 and cart["items"][0]["quantity"] == 3


def test_shipping_threshold_in_cart(client, seeded):
    cart = add(client, CASE, 1).get_json()["cart"]  # $25.00
    assert cart["shipping"] == 599 and cart["total"] == 3099
    assert cart["free_shipping_remaining"] == 2500
    cart = add(client, CASE, 1).get_json()["cart"]  # $50.00
    assert cart["shipping"] == 0 and cart["free_shipping_remaining"] == 0


def test_stock_limits_on_add(client, seeded):
    assert add(client, BASSLINE, 4).status_code == 200  # stock is 4
    r = add(client, BASSLINE, 1)
    assert r.status_code == 409 and "maximum" in r.get_json()["error"]
    assert r.get_json()["cart"]["count"] == 4  # error responses include the cart for resync


def test_stock_limit_partial_message(client, seeded):
    add(client, BASSLINE, 3)
    r = add(client, BASSLINE, 2)
    assert r.status_code == 409 and "Only 1 more" in r.get_json()["error"]


def test_per_order_limit(client, seeded):
    r = add(client, AURORA, 11)  # stock 30, limit 10 per line
    assert r.status_code == 400 and "at most 10" in r.get_json()["error"]
    assert add(client, AURORA, 10).status_code == 200
    assert add(client, AURORA, 1).status_code == 409


@pytest.mark.parametrize("quantity", [0, -1, 1.5, "abc", True, None, [1]])
def test_invalid_quantities_rejected(client, seeded, quantity):
    r = client.post("/api/cart/add", json={"product_id": pid(AURORA), "quantity": quantity})
    assert r.status_code == 400 and r.get_json()["ok"] is False
    assert cart_json(client)["count"] == 0


@pytest.mark.parametrize("payload", [{}, {"product_id": "x"}, {"product_id": True}, {"product_id": 99999}])
def test_invalid_products_rejected(client, seeded, payload):
    r = client.post("/api/cart/add", json=payload)
    assert r.status_code in (400, 404) and r.get_json()["ok"] is False


def test_non_json_body_rejected(client, seeded):
    r = client.post("/api/cart/add", data="not json", content_type="text/plain")
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_unavailable_products_cannot_be_added(client, seeded):
    assert add(client, "tripod-pro").status_code == 409  # out of stock
    product = Product.query.filter_by(slug=CASE).one()
    product.is_active = False
    db.session.commit()
    assert add(client, CASE).status_code == 404


def test_update_quantity(client, seeded):
    item_id = add(client, AURORA, 1).get_json()["cart"]["items"][0]["id"]
    r = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 5})
    assert r.status_code == 200 and r.get_json()["cart"]["count"] == 5
    assert client.patch(f"/api/cart/items/{item_id}", json={"quantity": 11}).status_code == 400
    assert client.patch(f"/api/cart/items/{item_id}", json={"quantity": 0}).status_code == 400
    assert client.patch(f"/api/cart/items/{item_id}", json={"quantity": "x"}).status_code == 400
    assert client.patch(f"/api/cart/items/{item_id}", json={}).status_code == 400
    assert cart_json(client)["count"] == 5


def test_update_respects_stock(client, seeded):
    item_id = add(client, BASSLINE, 2).get_json()["cart"]["items"][0]["id"]
    r = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 5})
    assert r.status_code == 409 and "Only 4" in r.get_json()["error"]
    assert r.get_json()["cart"]["items"][0]["quantity"] == 2


def test_remove_and_clear(client, seeded):
    add(client, AURORA, 1)
    cart = add(client, CASE, 2).get_json()["cart"]
    first = next(i for i in cart["items"] if i["name"].startswith("Aurora"))
    r = client.delete(f"/api/cart/items/{first['id']}")
    assert r.status_code == 200 and r.get_json()["cart"]["count"] == 2
    assert client.delete(f"/api/cart/items/{first['id']}").status_code == 404  # already gone
    r = client.delete("/api/cart")
    assert r.status_code == 200 and r.get_json()["cart"]["items"] == []
    assert cart_json(client)["total"] == 0


def test_clear_with_no_cart_is_fine(client, seeded):
    r = client.delete("/api/cart")
    assert r.status_code == 200 and r.get_json()["cart"]["count"] == 0


def test_cannot_touch_someone_elses_items(app, seeded):
    alice, bob = app.test_client(), app.test_client()
    item_id = add(alice, AURORA, 1).get_json()["cart"]["items"][0]["id"]
    add(bob, CASE, 1)
    assert bob.patch(f"/api/cart/items/{item_id}", json={"quantity": 3}).status_code == 404
    assert bob.delete(f"/api/cart/items/{item_id}").status_code == 404
    assert cart_json(alice)["items"][0]["quantity"] == 1


def test_guest_cart_is_private_to_its_session(app, seeded):
    alice, bob = app.test_client(), app.test_client()
    add(alice, AURORA, 2)
    assert cart_json(bob)["count"] == 0
    assert Cart.query.count() == 1


def test_csrf_is_enforced_on_cart_api(app, seeded):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    r = client.post("/api/cart/add", json={"product_id": 1, "quantity": 1})
    assert r.status_code == 400 and r.get_json()["ok"] is False
    assert Cart.query.count() == 0


# ------------------------------------------------------------ reconcile + page
def test_cart_page_states(client, seeded):
    empty = client.get("/cart")
    assert empty.status_code == 200 and b"Your cart is empty" in empty.data
    add(client, AURORA, 2)
    full = client.get("/cart")
    for marker in (b"data-cart-page", b"Aurora Wireless Headphones", b"data-remove-item",
                   b"Order summary", b"$298.00", b"data-clear-cart", b"unlocked free shipping"):
        assert marker in full.data, marker
    assert b"Your cart is empty" not in full.data


def test_cart_page_reduces_quantity_to_new_stock(client, seeded):
    add(client, BASSLINE, 4)
    Product.query.filter_by(slug=BASSLINE).one().stock_quantity = 2
    db.session.commit()
    page = client.get("/cart")
    assert b"we updated your quantity" in page.data
    assert cart_json(client)["items"][0]["quantity"] == 2


def test_cart_page_removes_unavailable_products(client, seeded):
    add(client, BASSLINE, 1)
    add(client, AURORA, 1)
    Product.query.filter_by(slug=BASSLINE).one().is_active = False
    db.session.commit()
    page = client.get("/cart")
    assert b"no longer available and was removed" in page.data
    assert [i["name"] for i in cart_json(client)["items"]] == ["Aurora Wireless Headphones"]


def test_api_cart_reports_notices(client, seeded):
    add(client, BASSLINE, 1)
    Product.query.filter_by(slug=BASSLINE).one().stock_quantity = 0
    db.session.commit()
    data = client.get("/api/cart").get_json()
    assert data["cart"]["items"] == [] and "no longer available" in data["notices"][0]


def test_cart_page_query_budget(client, seeded):
    add(client, AURORA, 1)
    add(client, CASE, 1)
    add(client, BASSLINE, 1)
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        r = client.get("/cart")
    finally:
        event.remove(db.engine, "before_cursor_execute", record)
    assert r.status_code == 200 and len(statements) <= 10, len(statements)


def test_header_badge_counts_guest_cart(client, seeded):
    add(client, AURORA, 2)
    add(client, CASE, 1)
    assert re.search(rb'data-badge="cart">\s*3\s*<', client.get("/").data)


def test_buy_now_button_points_somewhere_real(client, seeded):
    html = client.get(f"/product/{AURORA}").data
    assert b'data-redirect="/' in html


# ------------------------------------------------------------ logged-in carts + merge
def test_user_cart_persists_across_devices(app, seeded):
    phone, laptop = app.test_client(), app.test_client()
    login(phone)
    add(phone, AURORA, 2)
    login(laptop)
    assert cart_json(laptop)["count"] == 2


def test_guest_cart_becomes_user_cart_on_login(client, seeded):
    add(client, AURORA, 2)
    add(client, CASE, 1)
    login(client)
    cart = cart_json(client)
    assert cart["count"] == 3
    assert Cart.query.filter(Cart.user_id.is_(None)).count() == 0  # guest cart is gone
    assert re.search(rb'data-badge="cart">\s*3\s*<', client.get("/").data)


def test_login_merges_into_existing_user_cart_and_clamps_to_stock(client, seeded):
    login(client)
    add(client, AURORA, 1)
    add(client, BASSLINE, 3)
    client.post("/logout")
    add(client, AURORA, 2)       # guest
    add(client, BASSLINE, 3)     # 3 + 3 > stock 4
    add(client, CASE, 1)
    login(client)
    cart = {i["name"]: i["quantity"] for i in cart_json(client)["items"]}
    assert cart == {"Aurora Wireless Headphones": 3, "Bassline Portable Speaker": 4, "Phone Case Shield": 1}
    assert Cart.query.count() == 1


def test_register_adopts_guest_cart(client, seeded):
    add(client, AURORA, 1)
    client.post("/register", data={"name": "New Person", "email": "new@example.com",
                                   "password": "Secret123!", "confirm_password": "Secret123!"})
    user = User.query.filter_by(email="new@example.com").one()
    assert user.cart is not None and user.cart.items[0].quantity == 1
    assert cart_json(client)["count"] == 1


def test_logout_hides_user_cart(client, seeded):
    login(client)
    add(client, AURORA, 1)
    client.post("/logout")
    assert cart_json(client)["count"] == 0
    login(client)
    assert cart_json(client)["count"] == 1


# ------------------------------------------------------------ housekeeping
def test_purge_stale_guest_carts(app, seeded):
    product = Product.query.first()
    old = Cart(session_token="old-token", updated_at=utcnow() - timedelta(days=40))
    old.items.append(CartItem(product_id=product.id, quantity=1))
    fresh = Cart(session_token="fresh-token")
    fresh.items.append(CartItem(product_id=product.id, quantity=1))
    user = User.query.filter_by(email=CUSTOMER[0]).one()
    mine = Cart(user_id=user.id, updated_at=utcnow() - timedelta(days=400))  # user carts are never purged
    db.session.add_all([old, fresh, mine])
    db.session.commit()

    assert cart_service.purge_stale_guest_carts() == 1
    assert {c.session_token for c in Cart.query.filter(Cart.user_id.is_(None))} == {"fresh-token"}
    assert CartItem.query.count() == 1  # the stale cart's items were cascaded away
    assert Cart.query.filter_by(user_id=user.id).count() == 1
