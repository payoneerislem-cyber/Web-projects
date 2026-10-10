import re

import pytest
from sqlalchemy import event
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import Category, Product, Review, User
from app.models.mixins import utcnow
from app.services import catalog_service
from app.services.catalog_service import ProductFilters
from app.utils.money import to_cents
from seed import seed_database


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def cards(response) -> int:
    return response.data.count(b'class="product-card"')


def visible():
    return Product.query.filter(Product.is_active.is_(True), Product.deleted_at.is_(None))


def count_queries(client, url):
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        response = client.get(url)
    finally:
        event.remove(db.engine, "before_cursor_execute", record)
    return response, len(statements)


# ------------------------------------------------------------ product page
def test_product_page(client, seeded):
    r = client.get("/product/aurora-wireless-headphones")
    assert r.status_code == 200
    for marker in (b"Aurora Wireless Headphones", b"In stock", b"data-add-to-cart", b"data-buy-now",
                   b"application/ld+json", b'id="reviews"', b"Related products", b"Specifications"):
        assert marker in r.data, marker
    assert r.data.count(b"data-thumb") == 3
    assert b"Save 25%" in r.data


def test_product_page_404s(client, seeded):
    assert client.get("/product/nope").status_code == 404
    first, second = Product.query.order_by(Product.id).limit(2).all()
    first.is_active = False
    second.deleted_at = utcnow()
    db.session.commit()
    assert client.get(f"/product/{first.slug}").status_code == 404
    assert client.get(f"/product/{second.slug}").status_code == 404


def test_stock_states_and_quantity_limit(client, seeded):
    out = client.get("/product/tripod-pro")
    assert b"Out of stock" in out.data and b"Sold out" in out.data
    assert b"data-buy-now" not in out.data
    low = client.get("/product/bassline-portable-speaker")
    assert b"Only 4 left" in low.data and b'max="4"' in low.data
    plenty = client.get("/product/aurora-wireless-headphones")
    assert b'max="10"' in plenty.data  # capped by MAX_QTY_PER_ITEM


def test_rating_summary_matches_reviews(app, seeded):
    product = Product.query.filter(Product.review_count > 0).first()
    summary = catalog_service.rating_summary(product.id)
    assert summary["total"] == product.review_count
    assert summary["average"] == product.avg_rating
    assert [row["stars"] for row in summary["distribution"]] == [5, 4, 3, 2, 1]
    assert sum(row["count"] for row in summary["distribution"]) == summary["total"]


def test_hidden_reviews_are_not_counted(app, seeded):
    product = Product.query.filter(Product.review_count > 1).first()
    review = Review.query.filter_by(product_id=product.id).first()
    review.status = "rejected"
    db.session.commit()
    assert catalog_service.rating_summary(product.id)["total"] == product.review_count - 1


def test_related_products(app, seeded):
    product = Product.query.filter_by(slug="aurora-wireless-headphones").one()
    related = catalog_service.related_products(product)
    assert len(related) == 4
    assert all(p.id != product.id and p.category_id == product.category_id for p in related)


def test_recently_viewed(client, seeded):
    first = client.get("/product/nova-smart-watch")
    assert b"Recently viewed" not in first.data  # never lists the current product
    client.get("/product/pulse-fitness-band")
    third = client.get("/product/halo-ring-tracker")
    assert b"Recently viewed" in third.data
    section = third.data.split(b"Recently viewed")[1]
    assert b"Nova Smart Watch" in section and b"Pulse Fitness Band" in section


def test_public_name_hides_surname(app):
    assert User(email="a@example.com", name="Alice Morgan", password_hash="x").public_name == "Alice M."
    assert User(email="b@example.com", name="Plato", password_hash="x").public_name == "Plato"


def test_product_page_query_budget(client, seeded):
    response, n = count_queries(client, "/product/aurora-wireless-headphones")
    assert response.status_code == 200 and n <= 12, n


# ------------------------------------------------------------ filters
def test_category_filter(client, seeded):
    assert cards(client.get("/shop?category=audio&per_page=48")) == 5
    assert cards(client.get("/shop?category=does-not-exist&per_page=48")) == 30  # ignored


def test_price_filter(client, seeded):
    expected = visible().filter(Product.price >= 10000, Product.price <= 20000).count()
    assert expected > 0
    assert cards(client.get("/shop?min_price=100&max_price=200&per_page=48")) == expected
    # swapped bounds behave the same
    assert cards(client.get("/shop?min_price=200&max_price=100&per_page=48")) == expected


def test_brand_filter(client, seeded):
    sonic = visible().filter(Product.brand == "Sonic").count()
    both = visible().filter(Product.brand.in_(["Sonic", "Orbit"])).count()
    assert cards(client.get("/shop?brand=Sonic&per_page=48")) == sonic
    assert cards(client.get("/shop?brand=Sonic&brand=Orbit&per_page=48")) == both


def test_rating_and_stock_filters(client, seeded):
    rated = visible().filter(Product.avg_rating >= 4).count()
    in_stock = visible().filter(Product.stock_quantity > 0).count()
    assert 0 < rated < 30 and in_stock == 29
    assert cards(client.get("/shop?rating=4&per_page=48")) == rated
    assert cards(client.get("/shop?in_stock=1&per_page=48")) == in_stock


def test_combined_filters(client, seeded):
    expected = visible().filter(Product.brand == "Sonic", Product.price <= 15000,
                                Product.stock_quantity > 0).count()
    r = client.get("/shop?brand=Sonic&max_price=150&in_stock=1&per_page=48")
    assert cards(r) == expected


@pytest.mark.parametrize("query", [
    "min_price=abc", "max_price=-5", "min_price=NaN", "max_price=Infinity", "min_price=1e999999",
    "rating=99", "rating=abc", "sort=bogus", "per_page=abc", "brand=&brand=", "in_stock=maybe",
])
def test_invalid_filter_values_are_ignored(client, seeded, query):
    r = client.get(f"/shop?{query}")
    assert r.status_code == 200 and cards(r) == 12


def test_to_cents_rejects_non_finite():
    for bad in ("NaN", "Infinity", "-Infinity", "1e999999", "abc", ""):
        with pytest.raises(ValueError):
            to_cents(bad)
    assert to_cents("19.99") == 1999


def test_filter_state_survives_pagination(client, seeded):
    r = client.get("/shop?in_stock=1&sort=price_asc&per_page=12")
    assert b"in_stock=1" in r.data and b"sort=price_asc" in r.data and b'rel="next"' in r.data


def test_filter_form_reflects_state(client, seeded):
    html = client.get("/shop?brand=Sonic&rating=4&in_stock=1&min_price=50").data
    assert re.search(rb'name="brand" value="Sonic" checked', html)
    assert re.search(rb'name="rating" value="4" checked', html)
    assert re.search(rb'name="in_stock" value="1" checked', html)
    assert b'value="50"' in html
    assert b"Brand: Sonic" in html and b"In stock only" in html and b"Clear all" in html


def test_no_match_state_offers_clear(client, seeded):
    r = client.get("/shop?brand=Sonic&max_price=1")
    assert r.status_code == 200 and cards(r) == 0
    assert b"No products match your filters" in r.data and b"Clear filters" in r.data


def test_category_page_filters(client, seeded):
    expected = visible().join(Category).filter(Category.slug == "audio", Product.brand == "Resona").count()
    r = client.get("/category/audio?brand=Resona")
    assert r.status_code == 200 and cards(r) == expected


# ------------------------------------------------------------ sorting
def test_sorting(app, seeded):
    def items(sort):
        return catalog_service.list_products(ProductFilters(sort=sort), per_page=48).items

    prices = [p.price for p in items("price_asc")]
    assert prices == sorted(prices)
    prices = [p.price for p in items("price_desc")]
    assert prices == sorted(prices, reverse=True)
    ratings = [p.avg_rating for p in items("rating")]
    assert ratings == sorted(ratings, reverse=True)
    sales = [p.sales_count for p in items("popularity")]
    assert sales == sorted(sales, reverse=True)
    dates = [p.created_at for p in items("newest")]
    assert dates == sorted(dates, reverse=True)


def test_sort_select_reflects_choice(client, seeded):
    assert b'value="price_desc" selected' in client.get("/shop?sort=price_desc").data


def test_filters_roundtrip():
    args = MultiDict([("q", " red  shoes "), ("brand", "A"), ("brand", "A"), ("brand", "B"),
                      ("min_price", "10"), ("max_price", "99.5"), ("rating", "4"), ("in_stock", "1"),
                      ("sort", "price_asc")])
    f = ProductFilters.from_args(args)
    assert f.q == "red shoes" and f.brands == ("A", "B") and f.active_count == 5
    assert f.to_args() == {"q": "red shoes", "min_price": "10", "max_price": "99.5",
                           "brand": ["A", "B"], "rating": 4, "in_stock": 1, "sort": "price_asc"}
    assert f.without("brand", "A").brands == ("B",)
    assert f.without("price").min_price is None


# ------------------------------------------------------------ search
def names(response):
    return response.data


def test_search_by_name_brand_sku_category_description(client, seeded):
    assert b"Aurora Wireless Headphones" in client.get("/search?q=aurora").data
    assert b"Aurora Wireless Headphones" in client.get("/search?q=sonic").data  # brand
    assert b"Aurora Wireless Headphones" in client.get("/search?q=LUM-AUD-001").data  # SKU
    assert cards(client.get("/search?q=wearables&per_page=48")) == 5  # category name
    assert b"Pocket Gimbal" in client.get("/search?q=gimbal").data
    assert b"Foldable 3-axis" not in client.get("/search?q=zzzz").data


def test_search_all_words_must_match(client, seeded):
    r = client.get("/search", query_string={"q": "wireless headphones"})
    assert b"Aurora Wireless Headphones" in r.data and b"Slate Ultrabook" not in r.data


def test_search_relevance_orders_name_matches_first(app, seeded):
    f = ProductFilters(q="aurora", sort="relevance", default_sort="relevance")
    assert catalog_service.list_products(f).items[0].slug == "aurora-wireless-headphones"


def test_search_no_results_state(client, seeded):
    r = client.get("/search?q=zzzzqqq")
    assert r.status_code == 200
    assert b"No results for" in r.data and b"Best sellers" in r.data and b"Check the spelling" in r.data


def test_search_empty_query(client, seeded):
    r = client.get("/search")
    assert r.status_code == 200 and b"Search our store" in r.data
    assert client.get("/search?q=%20%20").status_code == 200


@pytest.mark.parametrize("q", ["%", "_", "100%", "a_b", "\\", "'; DROP TABLE products; --"])
def test_search_special_characters_are_literal(client, seeded, q):
    r = client.get("/search", query_string={"q": q})
    assert r.status_code == 200 and b"No results for" in r.data
    assert Product.query.count() == 30


def test_search_respects_visibility(client, seeded):
    product = Product.query.filter_by(slug="pocket-gimbal").one()
    product.is_active = False
    db.session.commit()
    assert b"Pocket Gimbal" not in client.get("/search?q=gimbal").data


def test_search_with_filters(client, seeded):
    # "sonic" is a substring of the brand "Sonic" AND of "Ultrasonic" in the
    # Aroma Diffuser's description, so substring search correctly returns both.
    term = "sonic"
    expected = sum(
        1 for p in visible().all()
        if p.stock_quantity > 0 and any(term in (text or "").lower() for text in (
            p.name, p.brand, p.sku, p.short_description, p.description, p.category.name))
    )
    r = client.get("/search?q=sonic&in_stock=1&per_page=48")
    assert expected >= 4 and cards(r) == expected
    assert b"Aroma Diffuser" in r.data and b"In stock only" in r.data


def test_search_escapes_query_in_page(client, seeded):
    r = client.get("/search", query_string={"q": "<script>alert(1)</script>"})
    assert b"<script>alert(1)</script>" not in r.data


def test_search_query_budget(client, seeded):
    response, n = count_queries(client, "/search?q=sonic")
    assert response.status_code == 200 and n <= 8, n
    response, n = count_queries(client, "/shop?brand=Sonic&rating=4")
    assert response.status_code == 200 and n <= 8, n


# ------------------------------------------------------------ live suggestions API
def test_suggest_api(client, seeded):
    data = client.get("/api/search/suggest?q=son").get_json()
    assert data["ok"] is True and 0 < len(data["products"]) <= 6
    first = data["products"][0]
    assert set(first) == {"name", "url", "price", "image", "category"}
    assert first["url"].startswith("/product/") and first["price"].startswith("$")

    cats = client.get("/api/search/suggest?q=wear").get_json()
    assert [c["name"] for c in cats["categories"]] == ["Wearables"]
    assert cats["categories"][0]["url"] == "/category/wearables"


def test_suggest_api_short_or_empty_queries(client, seeded):
    for url in ("/api/search/suggest", "/api/search/suggest?q=a", "/api/search/suggest?q=%20"):
        assert client.get(url).get_json() == {"ok": True, "products": [], "categories": []}
    nothing = client.get("/api/search/suggest?q=zzzzqqq").get_json()
    assert nothing["products"] == [] and nothing["categories"] == []


def test_suggest_api_hides_inactive(client, seeded):
    Product.query.filter_by(slug="pocket-gimbal").one().is_active = False
    db.session.commit()
    assert client.get("/api/search/suggest?q=gimbal").get_json()["products"] == []
