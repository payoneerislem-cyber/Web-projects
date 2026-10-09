import re

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import CartItem, Product, User, Wishlist, WishlistItem
from app.services import wishlist_service
from seed import seed_database

CUSTOMER = ("customer@example.com", "Customer12345")
ADMIN = ("admin@example.com", "Admin12345")
AURORA, NOVA, TRIPOD = "aurora-wireless-headphones", "nova-smart-watch", "tripod-pro"


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def pid(slug):
    return Product.query.filter_by(slug=slug).one().id


def login(client, creds=CUSTOMER):
    return client.post("/login", data={"email": creds[0], "password": creds[1]})


def toggle(client, slug):
    return client.post("/api/wishlist/toggle", json={"product_id": pid(slug)})


def customer():
    return User.query.filter_by(email=CUSTOMER[0]).one()


# ------------------------------------------------------------ access control
def test_guests_cannot_use_the_wishlist(client, seeded):
    r = client.post("/api/wishlist/toggle", json={"product_id": pid(AURORA)})
    assert r.status_code == 401 and r.get_json()["ok"] is False
    assert client.delete(f"/api/wishlist/{pid(AURORA)}").status_code == 401
    assert client.post(f"/api/wishlist/{pid(AURORA)}/move-to-cart").status_code == 401
    page = client.get("/account/wishlist")
    assert page.status_code == 302 and "/login" in page.headers["Location"]
    assert WishlistItem.query.count() == 0


def test_wishlists_are_private(app, seeded):
    alice, boss = app.test_client(), app.test_client()
    login(alice)
    toggle(alice, AURORA)
    login(boss, ADMIN)
    assert b"Your wishlist is empty" in boss.get("/account/wishlist").data
    boss.delete(f"/api/wishlist/{pid(AURORA)}")  # can't remove someone else's entry
    assert WishlistItem.query.count() == 1


def test_csrf_is_enforced(app, seeded):
    client = app.test_client()
    login(client)
    app.config["WTF_CSRF_ENABLED"] = True
    r = client.post("/api/wishlist/toggle", json={"product_id": pid(AURORA)})
    assert r.status_code == 400 and WishlistItem.query.count() == 0


# ------------------------------------------------------------ toggle / add / remove
def test_toggle_adds_then_removes(client, seeded):
    login(client)
    r = toggle(client, AURORA).get_json()
    assert r["in_wishlist"] is True and r["count"] == 1 and "Added" in r["message"]
    assert WishlistItem.query.count() == 1
    r = toggle(client, AURORA).get_json()
    assert r["in_wishlist"] is False and r["count"] == 0 and "Removed" in r["message"]
    assert WishlistItem.query.count() == 0


def test_no_duplicates(app, seeded):
    user = customer()
    assert wishlist_service.add(user, pid(AURORA)) is True
    assert wishlist_service.add(user, pid(AURORA)) is False
    assert WishlistItem.query.count() == 1
    # the database itself also refuses duplicates
    db.session.add(WishlistItem(wishlist_id=Wishlist.query.one().id, product_id=pid(AURORA)))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("payload", [{}, {"product_id": "x"}, {"product_id": True}, {"product_id": 1.5},
                                     {"product_id": "²"}, {"product_id": 99999}])
def test_invalid_product_ids(client, seeded, payload):
    login(client)
    r = client.post("/api/wishlist/toggle", json=payload)
    assert r.status_code in (400, 404) and r.get_json()["ok"] is False
    assert WishlistItem.query.count() == 0


def test_non_json_body(client, seeded):
    login(client)
    r = client.post("/api/wishlist/toggle", data="nope", content_type="text/plain")
    assert r.status_code == 400 and r.get_json()["ok"] is False


def test_unavailable_products_cannot_be_added(client, seeded):
    login(client)
    product = Product.query.filter_by(slug=NOVA).one()
    product.is_active = False
    db.session.commit()
    assert toggle(client, NOVA).status_code == 404


def test_out_of_stock_products_can_be_wishlisted(client, seeded):
    login(client)
    assert toggle(client, TRIPOD).get_json()["in_wishlist"] is True


def test_remove_endpoint_is_idempotent(client, seeded):
    login(client)
    toggle(client, AURORA)
    r = client.delete(f"/api/wishlist/{pid(AURORA)}")
    assert r.status_code == 200 and r.get_json()["count"] == 0
    assert client.delete(f"/api/wishlist/{pid(AURORA)}").status_code == 200


def test_wishlist_size_limit(app, client, seeded):
    app.config["MAX_WISHLIST_ITEMS"] = 2
    login(client)
    toggle(client, AURORA)
    toggle(client, NOVA)
    r = toggle(client, TRIPOD)
    assert r.status_code == 409 and "full" in r.get_json()["error"]
    assert WishlistItem.query.count() == 2


# ------------------------------------------------------------ move to cart
def test_move_to_cart(client, seeded):
    login(client)
    toggle(client, AURORA)
    r = client.post(f"/api/wishlist/{pid(AURORA)}/move-to-cart")
    data = r.get_json()
    assert r.status_code == 200 and data["count"] == 0 and data["cart_count"] == 1
    assert "Moved" in data["message"]
    assert WishlistItem.query.count() == 0
    assert CartItem.query.one().quantity == 1


def test_move_adds_to_existing_cart_line(client, seeded):
    login(client)
    client.post("/api/cart/add", json={"product_id": pid(AURORA), "quantity": 2})
    toggle(client, AURORA)
    assert client.post(f"/api/wishlist/{pid(AURORA)}/move-to-cart").get_json()["cart_count"] == 3


def test_move_out_of_stock_keeps_item(client, seeded):
    login(client)
    toggle(client, TRIPOD)
    r = client.post(f"/api/wishlist/{pid(TRIPOD)}/move-to-cart")
    assert r.status_code == 409 and r.get_json()["ok"] is False
    assert WishlistItem.query.count() == 1 and CartItem.query.count() == 0


def test_move_respects_cart_limit(client, seeded):
    login(client)
    client.post("/api/cart/add", json={"product_id": pid(AURORA), "quantity": 10})
    toggle(client, AURORA)
    r = client.post(f"/api/wishlist/{pid(AURORA)}/move-to-cart")
    assert r.status_code == 409
    assert WishlistItem.query.count() == 1 and CartItem.query.one().quantity == 10


def test_move_something_not_in_wishlist(client, seeded):
    login(client)
    assert client.post(f"/api/wishlist/{pid(AURORA)}/move-to-cart").status_code == 404
    assert CartItem.query.count() == 0


# ------------------------------------------------------------ pages and rendering
def test_wishlist_page_lists_items(client, seeded):
    login(client)
    toggle(client, AURORA)
    toggle(client, NOVA)
    r = client.get("/account/wishlist")
    assert r.status_code == 200 and b"data-wishlist-page" in r.data
    assert b"Aurora Wireless Headphones" in r.data and b"Nova Smart Watch" in r.data
    assert r.data.count(b"data-wishlist-card") == 2 and r.data.count(b"data-wishlist-move") == 2
    assert b"data-add-to-cart" not in r.data
    assert re.search(rb'data-badge="wishlist">\s*2\s*<', r.data)
    # newest first
    assert r.data.index(b"Nova Smart Watch") < r.data.index(b"Aurora Wireless Headphones")


def test_empty_wishlist_page(client, seeded):
    login(client)
    r = client.get("/account/wishlist")
    assert r.status_code == 200 and b"Your wishlist is empty" in r.data
    assert b'data-badge="wishlist" hidden' in r.data


def test_hearts_reflect_wishlist_state(client, seeded):
    login(client)
    toggle(client, AURORA)
    shop = client.get("/shop?per_page=48").data
    saved = rb'data-wishlist-toggle data-product-id="%d"[^>]*aria-pressed="true"' % pid(AURORA)
    other = rb'data-wishlist-toggle data-product-id="%d"[^>]*aria-pressed="false"' % pid(NOVA)
    assert re.search(saved, shop) and re.search(other, shop)
    assert b"Remove Aurora Wireless Headphones from wishlist" in shop
    page = client.get(f"/product/{AURORA}").data
    assert re.search(saved, page)


def test_guest_hearts_are_never_pressed(client, seeded):
    assert b'aria-pressed="true"' not in client.get("/shop?per_page=48").data


def test_unavailable_products_are_hidden_and_not_counted(client, seeded):
    login(client)
    toggle(client, AURORA)
    toggle(client, NOVA)
    Product.query.filter_by(slug=NOVA).one().is_active = False
    db.session.commit()
    page = client.get("/account/wishlist")
    assert b"Nova Smart Watch" not in page.data and b"Aurora Wireless Headphones" in page.data
    assert re.search(rb'data-badge="wishlist">\s*1\s*<', page.data)
    assert wishlist_service.product_ids(customer()) == {pid(AURORA)}


def test_wishlist_page_query_budget(client, seeded):
    login(client)
    for slug in (AURORA, NOVA, TRIPOD):
        toggle(client, slug)
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        r = client.get("/account/wishlist")
    finally:
        event.remove(db.engine, "before_cursor_execute", record)
    assert r.status_code == 200 and len(statements) <= 8, len(statements)


# ------------------------------------------------------------ fix in earlier code (cart input parsing)
def test_cart_rejects_odd_unicode_digits(client, seeded):
    r = client.post("/api/cart/add", json={"product_id": pid(AURORA), "quantity": "²"})
    assert r.status_code == 400 and r.get_json()["ok"] is False
