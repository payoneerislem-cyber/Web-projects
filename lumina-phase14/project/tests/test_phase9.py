import re

import pytest
from sqlalchemy import event, update

from app.extensions import db
from app.models import (Address, Cart, CartItem, Notification, Order, OrderItem, Product, User)
from app.services import cart_service, order_service, payment, pricing_service
from app.services.order_service import CheckoutError
from seed import seed_database

CUSTOMER = ("customer@example.com", "Customer12345")
ADMIN = ("admin@example.com", "Admin12345")
AURORA, BASSLINE, CASE, TRIPOD = ("aurora-wireless-headphones", "bassline-portable-speaker",
                                  "phone-case-shield", "tripod-pro")


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def product(slug):
    return Product.query.filter_by(slug=slug).one()


def login(client, creds=CUSTOMER):
    return client.post("/login", data={"email": creds[0], "password": creds[1]})


def add(client, slug, quantity=1):
    return client.post("/api/cart/add", json={"product_id": product(slug).id, "quantity": quantity})


def form(**overrides):
    data = {
        "full_name": "Demo Customer", "email": "customer@example.com", "phone": "+1 555 0100",
        "address_id": "new", "line1": "1 Test Street", "line2": "", "city": "Testville",
        "state": "TS", "postal_code": "12345", "country": "United States",
        "shipping_method": "standard", "payment_method": "cod", "demo_scenario": "approve",
        "notes": "", "accept_terms": "y",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def place(client, **overrides):
    return client.post("/checkout", data=form(**overrides))


def ready(client, *items):
    login(client)
    for slug, qty in (items or ((AURORA, 1),)):
        add(client, slug, qty)


# ------------------------------------------------------------ access + page
def test_checkout_requires_login(client, seeded):
    add(client, AURORA)
    for r in (client.get("/checkout"), client.post("/checkout", data=form())):
        assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert Order.query.count() == 0


def test_login_returns_to_checkout_with_the_guest_cart(client, seeded):
    add(client, AURORA, 2)
    r = client.post("/login?next=/checkout", data={"email": CUSTOMER[0], "password": CUSTOMER[1]})
    assert r.headers["Location"].endswith("/checkout")
    assert client.get("/checkout").status_code == 200  # the guest cart followed them


def test_empty_cart_redirects_to_cart(client, seeded):
    login(client)
    r = client.get("/checkout")
    assert r.status_code == 302 and r.headers["Location"].endswith("/cart")


def test_checkout_page(client, seeded):
    ready(client, (AURORA, 2))
    r = client.get("/checkout")
    assert r.status_code == 200
    for step in ("contact", "address", "shipping", "payment", "review"):
        assert f'data-step="{step}"'.encode() in r.data
    for text in (b"Standard delivery", b"Express delivery", b"Cash on Delivery", b"Demo card",
                 b"12 Market Street", b"Use a new address", b"Order summary", b"Aurora Wireless Headphones",
                 b"customer@example.com", b"$298.00", b"data-place-order"):
        assert text in r.data, text


def test_checkout_page_for_user_without_saved_addresses(client, seeded):
    Address.query.delete()
    db.session.commit()
    ready(client)
    r = client.get("/checkout")
    assert r.status_code == 200 and b'name="address_id" value="new"' in r.data


# ------------------------------------------------------------ placing orders
def test_place_cod_order(client, seeded):
    ready(client, (AURORA, 2), (CASE, 1))
    before = (product(AURORA).stock_quantity, product(CASE).stock_quantity,
              product(AURORA).sales_count)
    r = place(client, notes="Leave at the door")
    order = Order.query.one()
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/checkout/confirmation/{order.order_number}")
    assert re.fullmatch(r"LM-\d{6}-[A-Z2-9]{6}", order.order_number)

    assert (order.status, order.payment_status, order.payment_method) == ("pending", "pending", "cod")
    assert order.subtotal == 32300 and order.shipping_cost == 0 and order.tax == 0 and order.total == 32300
    assert order.customer_email == "customer@example.com" and order.notes == "Leave at the door"
    assert order.shipping_address["line1"] == "1 Test Street" and order.billing_address == order.shipping_address
    assert order.payment_reference == f"COD-{order.order_number}"
    names = {i.product_name_snapshot: (i.quantity, i.price_snapshot, i.subtotal) for i in order.items}
    assert names == {"Aurora Wireless Headphones": (2, 14900, 29800), "Phone Case Shield": (1, 2500, 2500)}

    assert product(AURORA).stock_quantity == before[0] - 2 and product(CASE).stock_quantity == before[1] - 1
    assert product(AURORA).sales_count == before[2] + 2
    assert CartItem.query.count() == 0  # cart emptied
    assert Notification.query.filter_by(type="order").count() == 1

    page = client.get(r.headers["Location"])
    assert page.status_code == 200 and order.order_number.encode() in page.data
    assert b"Cash on Delivery" in page.data and b"Payment: Pending" in page.data
    assert b"Leave at the door" in page.data


def test_saved_address_is_used_and_not_duplicated(client, seeded):
    ready(client)
    saved = Address.query.filter_by(user_id=User.query.filter_by(email=CUSTOMER[0]).one().id).one()
    place(client, address_id=str(saved.id), line1=None, city=None, postal_code=None, country=None)
    order = Order.query.one()
    assert order.shipping_address["line1"] == "12 Market Street"
    assert Address.query.count() == 1


def test_new_address_saved_only_when_asked(client, seeded):
    ready(client)
    place(client)
    assert Address.query.count() == 1
    add(client, AURORA)
    place(client, save_address="y")
    assert Address.query.count() == 2


def test_express_shipping(client, seeded):
    ready(client, (CASE, 1))  # $25.00
    place(client, shipping_method="express")
    order = Order.query.one()
    assert order.shipping_method == "express" and order.shipping_cost == 1499 and order.total == 3999


def test_standard_shipping_charged_below_threshold(client, seeded):
    ready(client, (CASE, 1))
    place(client)
    order = Order.query.one()
    assert order.shipping_cost == 599 and order.total == 3099
    assert b"$5.99" in client.get(f"/checkout/confirmation/{order.order_number}").data


def test_tax_is_applied_when_enabled(app, client, seeded):
    app.config["TAX_RATE"] = "0.10"
    ready(client, (CASE, 2))  # $50.00 -> free shipping
    place(client)
    order = Order.query.one()
    assert order.tax == 500 and order.total == 5500


def test_demo_payment_approved(client, seeded):
    ready(client)
    place(client, payment_method="demo_card", demo_scenario="approve")
    order = Order.query.one()
    assert order.payment_status == "paid" and order.status == "confirmed"
    assert order.payment_reference.startswith("DEMO-")


def test_demo_payment_declined_rolls_everything_back(client, seeded):
    ready(client, (AURORA, 2))
    stock = product(AURORA).stock_quantity
    r = place(client, payment_method="demo_card", demo_scenario="decline")
    assert r.status_code == 200 and b"declined" in r.data
    assert Order.query.count() == 0 and OrderItem.query.count() == 0
    assert product(AURORA).stock_quantity == stock  # stock restored
    assert CartItem.query.one().quantity == 2  # cart untouched
    assert Notification.query.filter_by(type="order").count() == 0
    # the customer can retry with another method
    assert place(client, payment_method="cod").status_code == 302 and Order.query.count() == 1


# ------------------------------------------------------------ validation
@pytest.mark.parametrize("overrides", [
    {"accept_terms": None},
    {"email": "not-an-email"},
    {"full_name": ""},
    {"phone": "abc"},
    {"address_id": "new", "line1": ""},
    {"address_id": "new", "city": ""},
    {"address_id": "new", "postal_code": ""},
    {"address_id": "999999"},
    {"address_id": None},
    {"shipping_method": "teleport"},
    {"shipping_method": None},
    {"payment_method": "bitcoin"},
    {"payment_method": None},
    {"notes": "x" * 501},
    {"line1": "x" * 201},
])
def test_invalid_submissions_create_nothing(client, seeded, overrides):
    ready(client)
    stock = product(AURORA).stock_quantity
    r = place(client, **overrides)
    assert r.status_code == 200
    assert Order.query.count() == 0 and CartItem.query.count() == 1
    assert product(AURORA).stock_quantity == stock


def test_errors_are_shown_and_values_kept(client, seeded):
    ready(client)
    r = place(client, accept_terms=None, line1="", full_name="Keep Me")
    assert b"You must accept the terms" in r.data and b"This field is required." in r.data
    assert b'value="Keep Me"' in r.data


def test_cannot_use_someone_elses_address(app, seeded):
    alice, boss = app.test_client(), app.test_client()
    ready(alice)
    login(boss, ADMIN)
    add(boss, AURORA)
    alices_address = Address.query.one()
    r = place(boss, address_id=str(alices_address.id))
    assert r.status_code == 200 and Order.query.count() == 0


def test_notes_are_escaped(client, seeded):
    ready(client)
    r = place(client, notes="<script>alert(1)</script>")
    page = client.get(r.headers["Location"])
    assert b"<script>alert(1)</script>" not in page.data and b"&lt;script&gt;" in page.data


def test_csrf_is_enforced(app, seeded):
    client = app.test_client()
    ready(client)
    app.config["WTF_CSRF_ENABLED"] = True
    r = client.post("/checkout", data=form())
    assert r.status_code == 400 and Order.query.count() == 0


# ------------------------------------------------------------ stock + prices
def test_stock_changed_since_cart_sends_customer_back(client, seeded):
    ready(client, (BASSLINE, 4))
    product(BASSLINE).stock_quantity = 2
    db.session.commit()
    r = place(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/cart")
    assert Order.query.count() == 0 and product(BASSLINE).stock_quantity == 2


def test_unavailable_product_blocks_checkout(client, seeded):
    ready(client, (AURORA, 1), (CASE, 1))
    product(CASE).is_active = False
    db.session.commit()
    r = place(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/cart")
    assert Order.query.count() == 0
    page = client.get("/cart")
    assert b"no longer available" in page.data


def test_prices_are_snapshotted(client, seeded):
    ready(client)
    place(client)
    order = Order.query.one()
    item = order.items[0]
    product(AURORA).price = 99900
    db.session.commit()
    db.session.refresh(order)
    assert item.price_snapshot == 14900 and order.total == 14900 + 0
    page = client.get(f"/checkout/confirmation/{order.order_number}").data
    assert b"$149.00" in page and b"$999.00" not in page


def test_price_change_before_checkout_is_charged_at_the_new_price(client, seeded):
    ready(client)
    product(AURORA).price = 12000
    db.session.commit()
    place(client)
    assert Order.query.one().total == 12000


def test_snapshot_survives_product_deletion(client, seeded):
    ready(client)
    place(client)
    db.session.delete(product(AURORA))
    db.session.commit()
    order = Order.query.one()
    assert order.items[0].product_id is None and order.items[0].product_name_snapshot == "Aurora Wireless Headphones"
    assert b"Aurora Wireless Headphones" in client.get(f"/checkout/confirmation/{order.order_number}").data


def test_reservation_never_oversells(app, seeded, monkeypatch):
    """Even if the last unit is bought *between* our stock check and the reservation,
    the conditional UPDATE refuses to go below zero and the order is rolled back."""
    from flask_login import login_user

    user = User.query.filter_by(email=CUSTOMER[0]).one()
    real_calculate = pricing_service.calculate

    def competing_purchase(*args, **kwargs):  # runs after validation, before reservation
        db.session.execute(update(Product).where(Product.slug == BASSLINE)
                           .values(stock_quantity=2).execution_options(synchronize_session=False))
        return real_calculate(*args, **kwargs)

    with app.test_request_context():
        login_user(user)
        cart_service.add_item(product(BASSLINE).id, 4)  # stock is 4
        cart = cart_service.get_cart()
        monkeypatch.setattr(pricing_service, "calculate", competing_purchase)
        with pytest.raises(CheckoutError) as err:
            order_service.create_order(
                user, cart, customer={"full_name": "A B", "email": "a@example.com", "phone": "123456"},
                address={"full_name": "A B", "phone": "123456", "line1": "x", "line2": "", "city": "c",
                         "state": "", "postal_code": "1", "country": "US"},
                shipping_method="standard", payment_method="cod")
        assert "sold out" in str(err.value) and err.value.needs_cart_fix
    assert Order.query.count() == 0 and OrderItem.query.count() == 0
    assert product(BASSLINE).stock_quantity >= 0


def test_stale_stock_is_caught_by_validation(app, seeded):
    from flask_login import login_user

    user = User.query.filter_by(email=CUSTOMER[0]).one()
    with app.test_request_context():
        login_user(user)
        cart_service.add_item(product(BASSLINE).id, 4)
        cart = cart_service.get_cart()
        product(BASSLINE).stock_quantity = 2
        db.session.commit()
        with pytest.raises(CheckoutError) as err:
            order_service.create_order(
                user, cart, customer={"full_name": "A B", "email": "a@example.com", "phone": "123456"},
                address={"full_name": "A B", "phone": "123456", "line1": "x", "line2": "", "city": "c",
                         "state": "", "postal_code": "1", "country": "US"},
                shipping_method="standard", payment_method="cod")
        assert "Only 2" in str(err.value)
    assert Order.query.count() == 0 and product(BASSLINE).stock_quantity == 2


def test_double_submit_creates_one_order(client, seeded):
    ready(client)
    first = place(client)
    second = place(client)
    assert first.status_code == 302 and "confirmation" in first.headers["Location"]
    assert second.status_code == 302 and second.headers["Location"].endswith("/cart")
    assert Order.query.count() == 1
    assert product(AURORA).stock_quantity == 29


# ------------------------------------------------------------ confirmation access
def test_confirmation_access_control(app, seeded):
    alice, boss, guest = app.test_client(), app.test_client(), app.test_client()
    ready(alice)
    url = place(alice).headers["Location"]
    assert alice.get(url).status_code == 200
    login(boss, ADMIN)
    assert boss.get(url).status_code == 404  # not their order
    assert guest.get(url).status_code == 302
    assert alice.get("/checkout/confirmation/LM-000000-AAAAAA").status_code == 404


def test_order_numbers_are_unique(client, seeded):
    ready(client)
    place(client)
    add(client, AURORA)
    place(client)
    numbers = [o.order_number for o in Order.query.all()]
    assert len(numbers) == 2 and len(set(numbers)) == 2


def test_confirmation_email(client, seeded, monkeypatch):
    sent = []
    monkeypatch.setattr(order_service, "send_email", lambda to, subject, body, reply_to=None: sent.append((to, subject, body)))
    ready(client)
    place(client)
    order = Order.query.one()
    assert len(sent) == 1 and sent[0][0] == "customer@example.com"
    assert order.order_number in sent[0][1] and "Aurora Wireless Headphones" in sent[0][2]


def test_failing_email_does_not_break_checkout(client, seeded, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(order_service, "send_email", boom)
    ready(client)
    assert place(client).status_code == 302 and Order.query.count() == 1


# ------------------------------------------------------------ providers + pricing
def test_payment_registry_and_providers(app):
    assert [p.key for p in payment.available_providers()] == ["cod", "demo_card"]
    assert payment.get_provider("cod").label == "Cash on Delivery"
    with pytest.raises(KeyError):
        payment.get_provider("paypal")
    order = Order(order_number="LM-TEST", shipping_address={})
    cod = payment.get_provider("cod").charge(order, {})
    assert cod.success and cod.status == "pending"
    demo = payment.get_provider("demo_card")
    ok, bad = demo.charge(order, {"scenario": "approve"}), demo.charge(order, {"scenario": "decline"})
    assert ok.success and ok.status == "paid" and not bad.success and bad.status == "failed"
    assert demo.refund(order).status == "refunded"


def test_shipping_methods(app):
    with app.test_request_context():
        assert pricing_service.calculate(2500, method="standard")["shipping"] == 599
        assert pricing_service.calculate(2500, method="express")["shipping"] == 1499
        assert pricing_service.calculate(9000, method="express")["shipping"] == 1499  # express is never free
        assert pricing_service.calculate(9000, method="standard")["shipping"] == 0
        with pytest.raises(ValueError):
            pricing_service.calculate(100, method="teleport")
        options = {o["key"]: o for o in pricing_service.shipping_options(2500)}
        assert options["express"]["total"] == 3999 and options["standard"]["shipping_formatted"] == "$5.99"
        assert pricing_service.shipping_options(9000)[0]["shipping_formatted"] == "Free"


def test_checkout_query_budget(client, seeded):
    ready(client, (AURORA, 1), (CASE, 1))
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        r = client.get("/checkout")
    finally:
        event.remove(db.engine, "before_cursor_execute", record)
    assert r.status_code == 200 and len(statements) <= 14, len(statements)
