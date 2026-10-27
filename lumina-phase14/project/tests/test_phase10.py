from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Notification, Order, User
from app.models.mixins import utcnow
from app.services import order_status_service
from app.services.order_status_service import OrderError
from seed import seed_database
from tests.flow import ADMIN, AURORA, CASE, CUSTOMER, login, place_order, product


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def fresh(order):
    return Order.query.filter_by(order_number=order.order_number).one()


def cancel(client, order, **kw):
    return client.post(f"/account/orders/{order.order_number}/cancel", **kw)


def test_order_pages_require_login(client, seeded):
    for path in ("/account/orders", "/account/orders/LM-000000-AAAAAA"):
        r = client.get(path)
        assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert client.post("/account/orders/LM-000000-AAAAAA/cancel").status_code == 302


def test_order_list_and_detail(app, seeded):
    alice = app.test_client()
    first = place_order(alice, ((AURORA, 1),))
    second = place_order(alice, ((CASE, 2),))
    page = alice.get("/account/orders")
    assert first.order_number.encode() in page.data and second.order_number.encode() in page.data
    assert page.data.index(second.order_number.encode()) < page.data.index(first.order_number.encode())  # newest first
    detail = alice.get(f"/account/orders/{first.order_number}")
    for text in (b"Order progress", b"Aurora Wireless Headphones", b"Cancel order", b"Cash on Delivery"):
        assert text in detail.data, text


def test_order_list_pagination(client, seeded):
    login(client)
    user = User.query.filter_by(email=CUSTOMER[0]).one()
    for i in range(12):
        db.session.add(Order(order_number=f"LM-T-{i:03d}", user_id=user.id, shipping_address={},
                             created_at=utcnow() - timedelta(minutes=i)))
    db.session.commit()
    assert client.get("/account/orders").data.count(b'class="order-row card"') == 10
    assert client.get("/account/orders?page=2").data.count(b'class="order-row card"') == 2
    r = client.get("/account/orders?page=99")
    assert r.status_code == 302 and "page=2" in r.headers["Location"]


def test_customers_cannot_see_or_cancel_other_orders(app, seeded):
    alice, boss = app.test_client(), app.test_client()
    order = place_order(alice)
    login(boss, ADMIN)
    assert boss.get(f"/account/orders/{order.order_number}").status_code == 404
    assert cancel(boss, order).status_code == 404
    assert fresh(order).status == "pending"


def test_customer_cancels_pending_order(client, seeded):
    order = place_order(client, ((AURORA, 2),))
    stock, sales = product(AURORA).stock_quantity, product(AURORA).sales_count
    assert cancel(client, order).status_code == 302
    order = fresh(order)
    assert order.status == "cancelled"
    assert product(AURORA).stock_quantity == stock + 2 and product(AURORA).sales_count == sales - 2
    assert Notification.query.filter_by(user_id=order.user_id, title="Order cancelled").count() == 1
    page = client.get(f"/account/orders/{order.order_number}")
    assert b"This order was cancelled" in page.data and b"Cancel order" not in page.data
    cancel(client, order)  # a second attempt must not restock again
    assert product(AURORA).stock_quantity == stock + 2


def test_cancelling_a_paid_order_refunds_it(client, seeded):
    order = place_order(client, payment_method="demo_card", demo_scenario="approve")
    assert (order.status, order.payment_status) == ("confirmed", "paid")
    cancel(client, order)
    order = fresh(order)
    assert (order.status, order.payment_status) == ("cancelled", "refunded")
    assert order.payment_reference.startswith("REFUND-")


def test_customer_cannot_cancel_once_processing(client, seeded):
    order = place_order(client)
    order.status = "processing"
    db.session.commit()
    r = cancel(client, order, follow_redirects=True)
    assert b"can no longer be cancelled" in r.data
    assert fresh(order).status == "processing"
    assert b"Cancel order" not in client.get(f"/account/orders/{order.order_number}").data


def test_status_rules_and_side_effects(app, client, seeded):
    order = place_order(client)
    with app.test_request_context():
        with pytest.raises(OrderError):
            order_status_service.change_status(order, "delivered")  # can't skip steps
        with pytest.raises(OrderError):
            order_status_service.change_status(order, "bogus")
        for status in ("confirmed", "processing", "shipped", "delivered"):
            order_status_service.change_status(order, status)
            assert order.status == status
        assert order.payment_status == "paid"  # cash collected on delivery
        with pytest.raises(OrderError):
            order_status_service.change_status(order, "cancelled")  # too late
        order_status_service.change_status(order, "refunded")
        assert order.payment_status == "refunded"
        with pytest.raises(OrderError):
            order_status_service.change_status(order, "pending")
    assert product(AURORA).stock_quantity == 30  # refund put the unit back
    notes = Notification.query.filter_by(user_id=order.user_id, type="order").all()
    assert len(notes) == 6 and all(n.link and n.link.endswith(order.order_number) for n in notes if n.title != "Order placed")


def test_restock_ignores_deleted_products(client, seeded):
    order = place_order(client)
    db.session.delete(product(AURORA))
    db.session.commit()
    cancel(client, order)
    assert fresh(order).status == "cancelled"
