import re
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Address, Notification, User
from app.models.mixins import utcnow
from seed import seed_database
from tests.flow import ADMIN, CUSTOMER, login, place_order


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def customer():
    return User.query.filter_by(email=CUSTOMER[0]).one()


def address_data(**overrides):
    data = {"label": "Work", "full_name": "Demo Customer", "phone": "+1 555 0100", "line1": "9 Office Road",
            "line2": "", "city": "Springfield", "state": "IL", "postal_code": "62701", "country": "United States"}
    data.update(overrides)
    return data


def add_notifications(user, count, read=False, prefix="Note"):
    for i in range(count):
        db.session.add(Notification(user_id=user.id, type="info", title=f"{prefix} {i}", message="m", is_read=read,
                                    created_at=utcnow() - timedelta(minutes=i)))
    db.session.commit()


@pytest.mark.parametrize("path", ["/account", "/account/orders", "/account/profile", "/account/profile/edit",
                                  "/account/password", "/account/addresses", "/account/notifications", "/account/wishlist"])
def test_account_pages_require_login(client, seeded, path):
    r = client.get(path)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_dashboard(client, seeded):
    login(client)
    page = client.get("/account")
    assert b"Hello, Demo" in page.data and b"No orders yet" in page.data
    order = place_order(client)
    page = client.get("/account")
    assert order.order_number.encode() in page.data and b"No orders yet" not in page.data


def test_profile_edit(client, seeded):
    login(client)
    assert b'value="Demo Customer"' in client.get("/account/profile/edit").data
    assert client.post("/account/profile/edit", data={"name": "New Name", "phone": "+1 555 0199"}).status_code == 302
    assert (customer().name, customer().phone) == ("New Name", "+1 555 0199")
    assert b"New Name" in client.get("/account/profile").data
    assert client.post("/account/profile/edit", data={"name": "A", "phone": "abc"}).status_code == 200
    assert customer().name == "New Name"
    client.post("/account/profile/edit", data={"name": "New Name", "phone": ""})
    assert customer().phone is None


def test_change_password(client, seeded):
    login(client)

    def change(**overrides):
        data = {"current_password": CUSTOMER[1], "new_password": "NewSecret456", "confirm_password": "NewSecret456"}
        data.update(overrides)
        return client.post("/account/password", data=data)

    assert b"incorrect" in change(current_password="Wrong123!").data
    assert b"Passwords must match" in change(confirm_password="Different1").data
    assert change(new_password="short", confirm_password="short").status_code == 200
    assert customer().check_password(CUSTOMER[1])  # nothing changed so far
    assert change().status_code == 302
    assert customer().check_password("NewSecret456") and not customer().check_password(CUSTOMER[1])
    assert Notification.query.filter_by(user_id=customer().id, type="security").count() == 1
    client.post("/logout")
    assert login(client, (CUSTOMER[0], "NewSecret456")).status_code == 302


def test_address_crud(client, seeded):
    login(client)
    existing = Address.query.filter_by(user_id=customer().id).one()
    assert existing.is_default
    assert client.post("/account/addresses", data=address_data()).status_code == 302
    new = Address.query.filter_by(line1="9 Office Road").one()
    assert not new.is_default
    page = client.get("/account/addresses")
    assert b"9 Office Road" in page.data and b"12 Market Street" in page.data

    client.post(f"/account/addresses/{new.id}/default")
    assert Address.query.get(new.id).is_default and not Address.query.get(existing.id).is_default

    assert client.post(f"/account/addresses/{new.id}/edit", data=address_data(line1="10 Office Road")).status_code == 302
    assert Address.query.get(new.id).line1 == "10 Office Road"

    client.post(f"/account/addresses/{new.id}/delete")  # deleting the default promotes the other one
    remaining = Address.query.filter_by(user_id=customer().id).all()
    assert len(remaining) == 1 and remaining[0].id == existing.id and remaining[0].is_default


def test_address_validation(client, seeded):
    login(client)
    r = client.post("/account/addresses", data=address_data(line1="", phone="x"))
    assert r.status_code == 200 and b"This field is required." in r.data
    assert Address.query.count() == 1


def test_cannot_touch_someone_elses_address(app, seeded):
    alice, boss = app.test_client(), app.test_client()
    login(alice)
    login(boss, ADMIN)
    addr = Address.query.one()
    assert boss.get(f"/account/addresses/{addr.id}/edit").status_code == 404
    for action in ("delete", "default"):
        assert boss.post(f"/account/addresses/{addr.id}/{action}").status_code == 404
    assert Address.query.count() == 1


def test_first_address_of_a_new_user_is_the_default(client, seeded):
    client.post("/register", data={"name": "New Person", "email": "new@example.com",
                                   "password": "Secret123!", "confirm_password": "Secret123!"})
    client.post("/account/addresses", data=address_data())
    assert Address.query.filter_by(line1="9 Office Road").one().is_default


def test_notifications_and_mark_read(client, seeded):
    login(client)
    add_notifications(customer(), 3)
    page = client.get("/account/notifications")
    assert page.data.count(b'class="card notice is-unread"') == 3 and b"Mark all as read" in page.data
    assert re.search(rb'Notifications <span class="badge badge-primary">3</span>', client.get("/").data)
    assert client.post("/account/notifications/read").status_code == 302
    assert Notification.query.filter_by(user_id=customer().id, is_read=False).count() == 0
    page = client.get("/account/notifications")
    assert b"is-unread" not in page.data and b"Mark all as read" not in page.data


def test_notifications_pagination_and_privacy(app, seeded):
    shopper, boss = app.test_client(), app.test_client()
    login(shopper)
    add_notifications(customer(), 25)
    add_notifications(User.query.filter_by(email=ADMIN[0]).one(), 1, prefix="Boss secret")
    assert shopper.get("/account/notifications").data.count(b'class="card notice') == 20
    page2 = shopper.get("/account/notifications?page=2")
    assert page2.data.count(b'class="card notice') == 5 and b"Boss secret" not in page2.data
    r = shopper.get("/account/notifications?page=99")
    assert r.status_code == 302 and "page=2" in r.headers["Location"]
