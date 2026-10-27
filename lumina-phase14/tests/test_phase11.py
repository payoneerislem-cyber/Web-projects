import re

import pytest

from app.extensions import db
from app.models import Review, User
from app.services import catalog_service
from seed import seed_database
from tests.flow import ADMIN, AURORA, CUSTOMER, login, place_order, product


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def delivered(client, slug=AURORA):
    order = place_order(client, ((slug, 1),))
    order.status = "delivered"
    db.session.commit()
    return order


def review(client, slug=AURORA, **overrides):
    data = {"rating": "5", "title": "Great", "content": "Really good."}
    data.update(overrides)
    return client.post(f"/product/{slug}/review", data={k: v for k, v in data.items() if v is not None})


def my_reviews():
    user = User.query.filter_by(email=CUSTOMER[0]).one()
    return Review.query.filter_by(user_id=user.id).all()


def test_guests_cannot_review(client, seeded):
    r = review(client)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert client.post(f"/product/{AURORA}/review/delete").status_code == 302


def test_must_buy_and_receive_the_product_first(client, seeded):
    login(client)
    r = review(client, follow_redirects=True)
    assert b"Only customers who received this product" in r.data and my_reviews() == []
    place_order(client)  # ordered but still pending
    review(client)
    assert my_reviews() == []


def test_review_after_delivery_updates_product_rating(client, seeded):
    delivered(client)
    pid = product(AURORA).id
    before = catalog_service.rating_summary(pid)["total"]
    r = review(client, rating="4", title="Solid", content="Works well.")
    assert r.status_code == 302 and r.headers["Location"].endswith("#reviews")
    saved = my_reviews()[0]
    assert saved.rating == 4 and saved.is_verified_purchase and saved.status == "approved"
    summary, item = catalog_service.rating_summary(pid), product(AURORA)
    assert summary["total"] == before + 1
    assert item.review_count == summary["total"] and item.avg_rating == summary["average"]
    page = client.get(f"/product/{AURORA}")
    assert b"Verified purchase" in page.data and b"Demo C." in page.data and b"Works well." in page.data


def test_reviewing_again_edits_instead_of_duplicating(client, seeded):
    delivered(client)
    review(client, rating="5", content="First thoughts.")
    review(client, rating="2", title="Changed my mind", content="Second thoughts.")
    reviews = my_reviews()
    assert len(reviews) == 1 and reviews[0].rating == 2 and reviews[0].content == "Second thoughts."
    item = product(AURORA)
    assert item.review_count == catalog_service.rating_summary(item.id)["total"]


def test_delete_own_review(client, seeded):
    delivered(client)
    pid = product(AURORA).id
    before = catalog_service.rating_summary(pid)["total"]
    review(client)
    assert client.post(f"/product/{AURORA}/review/delete").status_code == 302
    assert my_reviews() == []
    assert catalog_service.rating_summary(pid)["total"] == before and product(AURORA).review_count == before


@pytest.mark.parametrize("overrides", [
    {"rating": "0"}, {"rating": "6"}, {"rating": "abc"}, {"rating": ""}, {"rating": None}, {"rating": "3.5"},
    {"title": "t" * 151}, {"content": "c" * 2001},
])
def test_invalid_reviews_are_rejected(client, seeded, overrides):
    delivered(client)
    r = review(client, **overrides)
    assert r.status_code == 302 and my_reviews() == []


def test_missing_rating_explains_why(client, seeded):
    delivered(client)
    r = review(client, rating=None, follow_redirects=True)
    assert b"Please choose a rating" in r.data


def test_review_text_is_escaped(client, seeded):
    delivered(client)
    review(client, title="<b>bold</b>", content="<script>alert(1)</script>")
    page = client.get(f"/product/{AURORA}")
    assert b"<script>alert(1)</script>" not in page.data and b"&lt;script&gt;" in page.data
    assert b"<b>bold</b>" not in page.data


def test_form_visibility_for_each_visitor(app, seeded):
    guest, shopper = app.test_client(), app.test_client()
    assert b"Log in</a> to review" in guest.get(f"/product/{AURORA}").data
    login(shopper)
    page = shopper.get(f"/product/{AURORA}")
    assert b"review-form" not in page.data and b"Only customers who received" in page.data
    order = place_order(shopper)
    order.status = "delivered"
    db.session.commit()
    page = shopper.get(f"/product/{AURORA}")
    assert b"Write a review" in page.data and b'name="rating"' in page.data and b"Delete my review" not in page.data
    review(shopper, rating="3")
    page = shopper.get(f"/product/{AURORA}")
    assert b"Edit your review" in page.data and b"Delete my review" in page.data
    assert re.search(rb'name="rating" value="3" checked', page.data)


def test_delete_only_touches_your_own_review(app, seeded):
    shopper, boss = app.test_client(), app.test_client()
    delivered(shopper)
    review(shopper)
    login(boss, ADMIN)
    boss.post(f"/product/{AURORA}/review/delete")
    assert len(my_reviews()) == 1


def test_delivered_order_links_to_the_review_form(client, seeded):
    order = delivered(client)
    page = client.get(f"/account/orders/{order.order_number}")
    assert b"Write a review" in page.data and f"/product/{AURORA}#reviews".encode() in page.data
