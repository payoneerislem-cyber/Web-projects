import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import (Category, Coupon, NewsletterSubscriber, Product, Review, User)
from app.models.mixins import utcnow
from app.services import contact_service
from seed import SeedError, seed_database


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def cards(response) -> int:
    return response.data.count(b'class="product-card"')


def test_home_empty_state(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"catalog is empty" in r.data and b'class="hero"' in r.data


def test_seed_creates_data_and_is_consistent(app):
    summary = seed_database(write_images=False)
    assert summary["products"] == 30 and Product.query.count() == 30
    assert Category.query.count() == 6
    assert User.query.filter_by(email="admin@example.com").one().is_admin
    assert Coupon.query.filter_by(code="WELCOME10").one().discount_value == 10
    product = Product.query.filter(Product.review_count > 0).first()
    ratings = [r.rating for r in product.reviews]
    assert product.review_count == len(ratings)
    assert product.avg_rating == round(sum(ratings) / len(ratings), 1)
    assert Review.query.count() == summary["reviews"]


def test_seed_refuses_second_run_but_reset_works(app):
    seed_database(write_images=False)
    with pytest.raises(SeedError):
        seed_database(write_images=False)
    seed_database(reset=True, write_images=False)
    assert Product.query.count() == 30


def test_home_with_data(client, seeded):
    r = client.get("/")
    assert r.status_code == 200
    for text in (b"Aurora Wireless Headphones", b"Shop by category", b"Home &amp; Kitchen",
                 b"WELCOME10", b"Featured products", b"New arrivals", b"Best sellers",
                 b"Join our newsletter"):
        assert text in r.data, text
    assert b"catalog is empty" not in r.data


def test_shop_pagination(client, seeded):
    assert cards(client.get("/shop")) == 12
    assert cards(client.get("/shop?page=3")) == 6
    assert cards(client.get("/shop?page=abc")) == 12
    assert cards(client.get("/shop?per_page=24")) == 24
    assert cards(client.get("/shop?per_page=48")) == 30
    assert cards(client.get("/shop?per_page=999")) == 12  # not allowed -> default
    r = client.get("/shop?page=99")
    assert r.status_code == 302 and "page=3" in r.headers["Location"]


def test_pagination_markup(client, seeded):
    html = client.get("/shop?page=2").data
    assert b'rel="prev"' in html and b'rel="next"' in html
    assert b'aria-current="page">2<' in html


def test_inactive_and_deleted_products_hidden(client, seeded):
    first, second = Product.query.order_by(Product.id).limit(2).all()
    first.is_active = False
    second.deleted_at = utcnow()
    db.session.commit()
    assert cards(client.get("/shop?per_page=48")) == 28


def test_category_page(client, seeded):
    r = client.get("/category/audio")
    assert r.status_code == 200 and cards(r) == 5
    assert b"Aurora Wireless Headphones" in r.data and b"Slate Ultrabook" not in r.data
    assert client.get("/category/nope").status_code == 404
    Category.query.filter_by(slug="audio").one().is_active = False
    db.session.commit()
    assert client.get("/category/audio").status_code == 404


def test_shop_uses_few_queries(app, client, seeded):
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        client.get("/shop")
    finally:
        event.remove(db.engine, "before_cursor_execute", record)
    assert len(statements) <= 8, statements  # no N+1 on product cards


@pytest.mark.parametrize("path,text", [
    ("/about", b"About us"), ("/contact", b"Contact"), ("/faq", b"Frequently asked"),
    ("/terms", b"Terms"), ("/privacy", b"Privacy"),
])
def test_static_pages(client, path, text):
    r = client.get(path)
    assert r.status_code == 200 and text in r.data


def test_contact_form(client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        contact_service, "send_email",
        lambda to, subject, body, reply_to=None: sent.append((to, subject, body, reply_to)) or True)

    ok = client.post("/contact", data={"name": "Ada", "email": "ada@example.com",
                                       "subject": "Hello there",
                                       "message": "I have a question about shipping."})
    assert ok.status_code == 302 and len(sent) == 1 and sent[0][3] == "ada@example.com"

    bad = client.post("/contact", data={"name": "A", "email": "nope", "subject": "x", "message": "short"})
    assert bad.status_code == 200 and len(sent) == 1

    client.post("/contact", data={"name": "Eve", "email": "eve@example.com",
                                  "subject": "Hi\r\nBcc: x@evil.example",
                                  "message": "A long enough message here."})
    assert "\n" not in sent[-1][1] and "\r" not in sent[-1][1]


def test_newsletter_signup(client):
    r = client.post("/newsletter", data={"email": "Fan@Example.com", "next": "/"})
    assert r.status_code == 302
    client.post("/newsletter", data={"email": "fan@example.com"})  # duplicate: no error, no 2nd row
    assert NewsletterSubscriber.query.count() == 1
    assert NewsletterSubscriber.query.one().email == "fan@example.com"

    page = client.post("/newsletter", data={"email": "not-an-email"}, follow_redirects=True)
    assert b"valid email" in page.data
    assert NewsletterSubscriber.query.count() == 1


def test_newsletter_redirect_is_safe(client):
    r = client.post("/newsletter", data={"email": "a@example.com", "next": "https://evil.example.org"})
    assert "evil" not in r.headers["Location"]
