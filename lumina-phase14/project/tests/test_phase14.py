import io
import json
import re
from datetime import datetime

import pytest

from app.extensions import db
from app.models import Category, Coupon, CouponUsage, Notification, Product, Review, User
from app.services import catalog_service, contact_service, pricing_service, stats_service
from seed import seed_database
from tests.flow import (ADMIN, AURORA, BASSLINE, CASE, CUSTOMER, add_to_cart, login, place_order,
                        png_bytes, product)


@pytest.fixture()
def seeded(app):
    return seed_database(write_images=False)


def admin(app):
    client = app.test_client()
    login(client, ADMIN)
    return client


def audio():
    return Category.query.filter_by(slug="audio").one()


def product_form(category_id, **overrides):
    data = {"name": "Test Gadget", "sku": "TST-001", "category_id": str(category_id), "brand": "Acme",
            "price": "19.99", "compare_at_price": "29.99", "cost_price": "10", "stock_quantity": "25",
            "low_stock_threshold": "5", "short_description": "Short", "description": "Long text",
            "specs": "Color: Black\nWeight: 2 kg", "image_url": "", "is_active": "y", "is_featured": "y"}
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


# ------------------------------------------------------------ access control
ADMIN_PAGES = ["/admin", "/admin/products", "/admin/products/new", "/admin/categories", "/admin/categories/new",
               "/admin/orders", "/admin/users", "/admin/coupons", "/admin/coupons/new", "/admin/reviews",
               "/admin/inventory", "/admin/settings"]


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_pages_are_protected(app, seeded, path):
    assert app.test_client().get(path).status_code == 302
    shopper = app.test_client()
    login(shopper)
    assert shopper.get(path).status_code == 403
    assert admin(app).get(path).status_code == 200


@pytest.mark.parametrize("path", ["/admin/products/1/delete", "/admin/products/1/toggle", "/admin/orders/1/status",
                                  "/admin/users/2/role", "/admin/coupons/1/delete", "/admin/reviews/1/delete",
                                  "/admin/inventory/1", "/admin/categories/1/delete", "/admin/settings"])
def test_admin_actions_are_protected(app, seeded, path):
    assert app.test_client().post(path).status_code == 302
    shopper = app.test_client()
    login(shopper)
    assert shopper.post(path, data={"field": "active", "status": "x"}).status_code == 403
    assert Product.query.get(1).deleted_at is None


def test_csrf_is_enforced_on_admin_posts(app, seeded):
    boss = admin(app)
    app.config["WTF_CSRF_ENABLED"] = True
    p = product(AURORA)
    assert boss.post(f"/admin/products/{p.id}/delete").status_code == 400
    assert product(AURORA).deleted_at is None


def test_next_parameter_is_validated(app, seeded):
    boss, p = admin(app), product(AURORA)
    r = boss.post(f"/admin/products/{p.id}/toggle", data={"field": "featured", "next": "https://evil.example/x"})
    assert r.status_code == 302 and "evil" not in r.headers["Location"]


# ------------------------------------------------------------ dashboard
def test_dashboard_numbers_and_chart(app, seeded):
    shopper, boss = app.test_client(), admin(app)
    place_order(shopper, ((AURORA, 1),))
    gone = place_order(shopper, ((CASE, 1),))
    shopper.post(f"/account/orders/{gone.order_number}/cancel")
    stats = stats_service.overview()
    assert stats["total_sales"] == 14900 and stats["orders"] == 2 and stats["pending"] == 1
    assert dict(stats["status_counts"])["cancelled"] == 1
    assert len(stats["series"]) == 14 and sum(p["total"] for p in stats["series"]) == 14900
    assert stats["customers"] == User.query.filter_by(role="customer").count()
    page = boss.get("/admin")
    assert b"$149.00" in page.data
    raw = re.search(rb'<script type="application/json" id="chart-data">(.*?)</script>', page.data, re.S).group(1)
    payload = json.loads(raw)
    assert len(payload["series"]) == 14 and payload["currency"] == "USD"


# ------------------------------------------------------------ products
def test_create_product(app, seeded):
    boss = admin(app)
    r = boss.post("/admin/products/new", data=product_form(audio().id))
    assert r.status_code == 302
    p = Product.query.filter_by(sku="TST-001").one()
    assert (p.slug, p.price, p.compare_at_price, p.cost_price) == ("test-gadget", 1999, 2999, 1000)
    assert p.stock_quantity == 25 and p.is_active and p.is_featured and not p.is_new
    assert p.specs == {"Color": "Black", "Weight": "2 kg"} and p.category_id == audio().id
    assert b"Test Gadget" in app.test_client().get(f"/product/{p.slug}").data
    boss.post("/admin/products/new", data=product_form(audio().id, sku="TST-002"))
    assert Product.query.filter_by(sku="TST-002").one().slug == "test-gadget-2"
    dup = boss.post("/admin/products/new", data=product_form(audio().id))
    assert dup.status_code == 200 and b"already used" in dup.data


@pytest.mark.parametrize("overrides, text", [
    ({"price": "abc"}, b"Enter a valid amount"), ({"price": "-5"}, b"allowed range"), ({"price": ""}, b"required"),
    ({"price": "NaN"}, b"Enter a valid amount"), ({"compare_at_price": "5.00"}, b"Must be higher"),
    ({"stock_quantity": "-1"}, b"Number must be at least 0"), ({"stock_quantity": "abc"}, b"Not a valid integer"),
    ({"name": ""}, b"required"), ({"sku": "bad sku!"}, b"Use letters"),
    ({"specs": "no colon here"}, b"Line 1 must look like"), ({"image_url": "http://x.example/a.png"}, b"Use a full https"),
    ({"category_id": "99999"}, b"Not a valid choice"),
])
def test_product_validation(app, seeded, overrides, text):
    r = admin(app).post("/admin/products/new", data=product_form(audio().id, **overrides))
    assert r.status_code == 200 and text in r.data
    assert Product.query.filter_by(sku="TST-001").count() == 0


def test_edit_keeps_slug_and_prefills(app, seeded):
    boss, p = admin(app), product(AURORA)
    r = boss.post(f"/admin/products/{p.id}/edit", data=product_form(
        p.category_id, name="Aurora Renamed", sku=p.sku, price="120", compare_at_price=None,
        stock_quantity="7", is_featured=None))
    assert r.status_code == 302
    p = product(AURORA)
    assert (p.name, p.slug, p.price, p.compare_at_price, p.stock_quantity) == (
        "Aurora Renamed", "aurora-wireless-headphones", 12000, None, 7) and not p.is_featured
    assert b'value="120.00"' in boss.get(f"/admin/products/{p.id}/edit").data


def test_product_images(app, seeded, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    boss = admin(app)
    files = [(io.BytesIO(png_bytes()), "a.png", "image/png"), (io.BytesIO(png_bytes((30, 30))), "b.png", "image/png")]
    boss.post("/admin/products/new", data=product_form(audio().id, images=files))
    p = Product.query.filter_by(sku="TST-001").one()
    assert len(p.images) == 2 and p.main_image == p.images[0].url
    assert p.main_image.startswith("/static/uploads/products/")
    assert len(list((tmp_path / "products").iterdir())) == 2
    first = p.images[0]
    boss.post(f"/admin/products/{p.id}/edit", data={**product_form(audio().id), "delete_image": str(first.id)})
    p = Product.query.get(p.id)
    assert len(p.images) == 1 and p.main_image == p.images[0].url
    assert len(list((tmp_path / "products").iterdir())) == 1  # the removed file is gone from disk


@pytest.mark.parametrize("filename, mimetype, kind, text", [
    ("x.png", "image/png", "junk", b"valid image"), ("x.exe", "image/png", "png", b"Only JPG, PNG or WebP"),
    ("x.png", "text/plain", "png", b"supported image"), ("x.gif", "image/gif", "png", b"Only JPG, PNG or WebP"),
])
def test_bad_uploads_are_rejected(app, seeded, tmp_path, filename, mimetype, kind, text):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    content = png_bytes() if kind == "png" else b"junk"
    r = admin(app).post("/admin/products/new", data=product_form(
        audio().id, images=[(io.BytesIO(content), filename, mimetype)]))
    assert r.status_code == 200 and text in r.data
    assert Product.query.filter_by(sku="TST-001").count() == 0 and not list(tmp_path.rglob("*"))


def test_oversized_upload_is_refused(app, seeded, tmp_path):
    from PIL import Image

    app.config["UPLOAD_FOLDER"], app.config["MAX_CONTENT_LENGTH"] = str(tmp_path), 2000
    buffer = io.BytesIO()
    Image.effect_noise((120, 120), 90).save(buffer, "PNG")
    r = admin(app).post("/admin/products/new", data=product_form(
        audio().id, images=[(io.BytesIO(buffer.getvalue()), "big.png", "image/png")]))
    assert r.status_code == 413 and Product.query.filter_by(sku="TST-001").count() == 0


def test_soft_delete_keeps_history_and_can_be_restored(app, seeded):
    shopper, boss = app.test_client(), admin(app)
    order = place_order(shopper, ((AURORA, 1),))
    p = product(AURORA)
    boss.post(f"/admin/products/{p.id}/delete")
    p = product(AURORA)
    assert p.deleted_at is not None and not p.is_active
    assert app.test_client().get(f"/product/{p.slug}").status_code == 404
    detail = shopper.get(f"/account/orders/{order.order_number}")
    assert detail.status_code == 200 and b"Aurora Wireless Headphones" in detail.data
    assert b"Aurora Wireless Headphones" not in boss.get("/admin/products?q=aurora").data
    assert b"Aurora Wireless Headphones" in boss.get("/admin/products?status=deleted").data
    boss.post(f"/admin/products/{p.id}/restore")
    assert product(AURORA).deleted_at is None and not product(AURORA).is_active
    boss.post(f"/admin/products/{p.id}/toggle", data={"field": "active"})
    assert app.test_client().get(f"/product/{p.slug}").status_code == 200


def test_toggle_flags(app, seeded):
    boss, p = admin(app), product(AURORA)
    for field, attr in (("featured", "is_featured"), ("new", "is_new"), ("best_seller", "is_best_seller"), ("active", "is_active")):
        before = getattr(product(AURORA), attr)
        boss.post(f"/admin/products/{p.id}/toggle", data={"field": field})
        assert getattr(product(AURORA), attr) is (not before)
    r = boss.post(f"/admin/products/{p.id}/toggle", data={"field": "bogus"}, follow_redirects=True)
    assert b"Unknown option" in r.data


def test_product_list_filters_and_paging(app, seeded):
    boss = admin(app)
    low = boss.get("/admin/products?status=low").data
    assert b"Bassline Portable Speaker" in low and b"Tripod Pro" in low and b"Slate Ultrabook" not in low
    found = boss.get("/admin/products?q=aurora").data
    assert b"Aurora Wireless Headphones" in found and b"Slate Ultrabook" not in found
    assert boss.get("/admin/products").data.count(b'class="cell-product"') == 20
    assert boss.get("/admin/products?page=2").data.count(b'class="cell-product"') == 10
    product(AURORA).is_active = False
    db.session.commit()
    assert b"Aurora Wireless Headphones" in boss.get("/admin/products?status=inactive").data


def test_admin_pages_escape_names(app, seeded):
    boss = admin(app)
    name = "<img src=x onerror=alert(1)>"
    boss.post("/admin/products/new", data=product_form(audio().id, name=name))
    slug = Product.query.filter_by(sku="TST-001").one().slug
    for page in (boss.get("/admin/products"), app.test_client().get(f"/product/{slug}"), app.test_client().get("/shop")):
        assert name.encode() not in page.data
    assert b"&lt;img src=x" in boss.get("/admin/products").data


# ------------------------------------------------------------ categories
def test_category_crud(app, seeded, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    boss = admin(app)
    assert boss.post("/admin/categories/new", data={"name": "Gaming", "description": "Games", "is_active": "y"}).status_code == 302
    cat = Category.query.filter_by(name="Gaming").one()
    assert cat.slug == "gaming"
    dup = boss.post("/admin/categories/new", data={"name": "Gaming"})
    assert dup.status_code == 200 and b"already exists" in dup.data
    boss.post(f"/admin/categories/{cat.id}/edit", data={"name": "Gaming & VR", "description": "x",
              "image": (io.BytesIO(png_bytes()), "c.png", "image/png")})
    cat = Category.query.get(cat.id)
    assert (cat.name, cat.slug, cat.is_active) == ("Gaming & VR", "gaming", False)
    assert cat.image.startswith("/static/uploads/categories/")
    r = boss.post(f"/admin/categories/{audio().id}/delete", follow_redirects=True)
    assert b"still has 5 products" in r.data and audio() is not None
    boss.post(f"/admin/categories/{cat.id}/delete")
    assert Category.query.filter_by(id=cat.id).count() == 0 and not list((tmp_path / "categories").iterdir())


# ------------------------------------------------------------ orders
def test_order_workflow(app, seeded):
    shopper, boss = app.test_client(), admin(app)
    order = place_order(shopper)
    detail = boss.get(f"/admin/orders/{order.id}")
    assert order.order_number.encode() in detail.data and b"Update status" in detail.data

    r = boss.post(f"/admin/orders/{order.id}/status", data={"status": "delivered"}, follow_redirects=True)
    assert b"become delivered" in r.data and Order_status(order) == "pending"
    assert b"Unknown order status" in boss.post(f"/admin/orders/{order.id}/status", data={"status": "bogus"},
                                                follow_redirects=True).data
    for status in ("confirmed", "processing", "shipped", "delivered"):
        boss.post(f"/admin/orders/{order.id}/status", data={"status": status})
        assert Order_status(order) == status
    assert order_payment(order) == "paid"
    assert Notification.query.filter_by(user_id=order.user_id, type="order").count() == 5
    assert b"Write a review" in shopper.get(f"/account/orders/{order.order_number}").data
    assert b"no further changes" not in boss.get(f"/admin/orders/{order.id}").data  # delivered can still be refunded


def Order_status(order):
    from app.models import Order
    return Order.query.get(order.id).status


def order_payment(order):
    from app.models import Order
    return Order.query.get(order.id).payment_status


def test_admin_cancel_restocks_and_refunds(app, seeded):
    shopper, boss = app.test_client(), admin(app)
    order = place_order(shopper, payment_method="demo_card", demo_scenario="approve")
    stock = product(AURORA).stock_quantity
    boss.post(f"/admin/orders/{order.id}/status", data={"status": "cancelled"})
    assert (Order_status(order), order_payment(order)) == ("cancelled", "refunded")
    assert product(AURORA).stock_quantity == stock + 1
    assert b"no further changes" in boss.get(f"/admin/orders/{order.id}").data


def test_order_list_filters(app, seeded):
    shopper, boss = app.test_client(), admin(app)
    a = place_order(shopper, ((AURORA, 1),))
    b = place_order(shopper, ((CASE, 1),))
    boss.post(f"/admin/orders/{b.id}/status", data={"status": "confirmed"})
    only = boss.get("/admin/orders?status=confirmed").data
    assert b.order_number.encode() in only and a.order_number.encode() not in only
    found = boss.get(f"/admin/orders?q={a.order_number}").data
    assert a.order_number.encode() in found and b.order_number.encode() not in found
    both = boss.get("/admin/orders?status=bogus&q=customer@example").data
    assert a.order_number.encode() in both and b.order_number.encode() in both


# ------------------------------------------------------------ users
def test_user_management(app, seeded):
    boss = admin(app)
    target = User.query.filter_by(email=CUSTOMER[0]).one()
    me = User.query.filter_by(email=ADMIN[0]).one()
    assert b"customer@example.com" in boss.get("/admin/users?q=customer@").data
    boss.post(f"/admin/users/{target.id}/toggle-active")
    assert not User.query.get(target.id).is_active
    assert b"disabled" in login(app.test_client()).data
    boss.post(f"/admin/users/{target.id}/toggle-active")
    assert User.query.get(target.id).is_active
    boss.post(f"/admin/users/{target.id}/role", data={"role": "bogus"})
    assert User.query.get(target.id).role == "customer"
    boss.post(f"/admin/users/{target.id}/role", data={"role": "admin"})
    newcomer = app.test_client()
    login(newcomer)
    assert newcomer.get("/admin").status_code == 200
    boss.post(f"/admin/users/{me.id}/toggle-active")  # you can't lock yourself out
    boss.post(f"/admin/users/{me.id}/role", data={"role": "customer"})
    me = User.query.get(me.id)
    assert me.is_active and me.is_admin


# ------------------------------------------------------------ coupons
def coupon_form(**overrides):
    data = {"code": "SUMMER15", "description": "Summer", "discount_type": "percentage", "discount_value": "15",
            "minimum_order": "20", "maximum_discount": "30", "usage_limit": "100", "per_user_limit": "2",
            "start_date": "2026-06-01", "expiry_date": "2026-09-30", "is_active": "y"}
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def test_coupon_create_edit_toggle_delete(app, seeded):
    boss = admin(app)
    assert boss.post("/admin/coupons/new", data=coupon_form()).status_code == 302
    c = Coupon.query.filter_by(code="SUMMER15").one()
    assert (c.discount_value, c.minimum_order, c.maximum_discount, c.usage_limit, c.per_user_limit) == (15, 2000, 3000, 100, 2)
    assert c.start_date == datetime(2026, 6, 1) and c.expiry_date == datetime(2026, 9, 30, 23, 59, 59) and c.is_active

    boss.post("/admin/coupons/new", data=coupon_form(code="five", discount_type="fixed", discount_value="5.00",
                                                     minimum_order="", maximum_discount="", usage_limit=""))
    five = Coupon.query.filter_by(code="FIVE").one()  # codes are stored upper-case
    assert (five.discount_value, five.minimum_order, five.maximum_discount, five.usage_limit) == (500, 0, None, None)

    page = boss.get(f"/admin/coupons/{c.id}/edit")
    assert b'value="15"' in page.data and b'value="20.00"' in page.data
    boss.post(f"/admin/coupons/{c.id}/edit", data=coupon_form(discount_value="20"))
    assert Coupon.query.get(c.id).discount_value == 20
    boss.post(f"/admin/coupons/{c.id}/toggle")
    assert not Coupon.query.get(c.id).is_active

    dup = boss.post("/admin/coupons/new", data=coupon_form())
    assert dup.status_code == 200 and b"already exists" in dup.data
    boss.post(f"/admin/coupons/{five.id}/delete")
    assert Coupon.query.filter_by(code="FIVE").count() == 0
    used = Coupon.query.filter_by(code="WELCOME10").one()
    used.used_count = 1
    db.session.commit()
    r = boss.post(f"/admin/coupons/{used.id}/delete", follow_redirects=True)
    assert b"has been used" in r.data and Coupon.query.filter_by(code="WELCOME10").count() == 1


@pytest.mark.parametrize("overrides, text", [
    ({"discount_value": "150"}, b"whole percentage"), ({"discount_value": "10.5"}, b"whole percentage"),
    ({"discount_value": "abc"}, b"whole percentage"), ({"discount_value": "NaN"}, b"whole percentage"),
    ({"discount_value": "Infinity"}, b"whole percentage"), ({"discount_value": "0"}, b"whole percentage"),
    ({"discount_type": "fixed", "discount_value": "0"}, b"allowed range"),
    ({"discount_type": "fixed", "discount_value": "abc"}, b"Enter a valid amount"),
    ({"code": "ab"}, b"3-50"), ({"code": "bad code"}, b"3-50"),
    ({"start_date": "2026-09-01", "expiry_date": "2026-08-01"}, b"on or after the start date"),
    ({"per_user_limit": "0"}, b"Number must be at least 1"), ({"usage_limit": "0"}, b"Number must be at least 1"),
    ({"minimum_order": "abc"}, b"Enter a valid amount"),
])
def test_coupon_validation(app, seeded, overrides, text):
    r = admin(app).post("/admin/coupons/new", data=coupon_form(**overrides))
    assert r.status_code == 200 and text in r.data
    assert Coupon.query.filter_by(code="SUMMER15").count() == 0


# ------------------------------------------------------------ reviews + inventory
def test_review_moderation(app, seeded):
    shopper, boss = app.test_client(), admin(app)
    order = place_order(shopper)
    order.status = "delivered"
    db.session.commit()
    shopper.post(f"/product/{AURORA}/review", data={"rating": "1", "title": "Bad", "content": "unique-bad-text"})
    review = Review.query.filter_by(user_id=order.user_id).one()
    pid = product(AURORA).id
    boss.post(f"/admin/reviews/{review.id}/status", data={"status": "rejected"})
    summary = catalog_service.rating_summary(pid)
    assert product(AURORA).review_count == summary["total"]
    assert b"unique-bad-text" not in app.test_client().get(f"/product/{AURORA}").data
    assert b"unique-bad-text" in boss.get("/admin/reviews?status=rejected&q=unique-bad").data
    boss.post(f"/admin/reviews/{review.id}/status", data={"status": "approved"})
    assert b"unique-bad-text" in app.test_client().get(f"/product/{AURORA}").data
    boss.post(f"/admin/reviews/{review.id}/status", data={"status": "bogus"})
    assert Review.query.get(review.id).status == "approved"
    boss.post(f"/admin/reviews/{review.id}/delete")
    assert Review.query.filter_by(id=review.id).count() == 0
    assert product(AURORA).review_count == catalog_service.rating_summary(pid)["total"]


def test_inventory(app, seeded):
    boss, p = admin(app), product(BASSLINE)
    assert boss.post(f"/admin/inventory/{p.id}", data={"stock_quantity": "40", "low_stock_threshold": "10"}).status_code == 302
    p = product(BASSLINE)
    assert (p.stock_quantity, p.low_stock_threshold) == (40, 10)
    for stock, threshold in (("abc", "5"), ("-1", "5"), ("5", "-1"), ("1000001", "5"), ("5", "100001"), ("", "")):
        boss.post(f"/admin/inventory/{p.id}", data={"stock_quantity": stock, "low_stock_threshold": threshold})
        assert (product(BASSLINE).stock_quantity, product(BASSLINE).low_stock_threshold) == (40, 10)
    out = boss.get("/admin/inventory?level=out").data
    assert b"Tripod Pro" in out and b"Aurora Wireless Headphones" not in out and b"Out of stock (1)" in out
    assert b"Bassline Portable Speaker" not in boss.get("/admin/inventory?level=low").data


# ------------------------------------------------------------ settings
def settings_form(**overrides):
    data = {"announcement_text": "Big sale today", "free_shipping_threshold": "30", "standard_shipping_rate": "3.50",
            "express_shipping_rate": "9", "tax_rate": "10", "contact_email": "help@example.com"}
    data.update(overrides)
    return data


def test_settings_change_how_the_store_behaves(app, seeded, monkeypatch):
    boss, shopper = admin(app), app.test_client()
    assert app.config["ANNOUNCEMENT_TEXT"].encode() in shopper.get("/").data
    assert boss.post("/admin/settings", data=settings_form()).status_code == 302
    assert b"Big sale today" in shopper.get("/").data

    cart = add_to_cart(shopper, CASE, 1).get_json()["cart"]  # $25.00 < $30 threshold
    assert (cart["shipping"], cart["tax"], cart["total"]) == (350, 250, 3100)
    cart = add_to_cart(shopper, CASE, 1).get_json()["cart"]  # $50.00 >= $30: free shipping
    assert (cart["shipping"], cart["tax"], cart["total"]) == (0, 500, 5500)
    with app.test_request_context():
        assert pricing_service.calculate(2500, method="express")["shipping"] == 900

    page = boss.get("/admin/settings").data
    assert b'value="3.50"' in page and b'value="10"' in page and b'value="help@example.com"' in page
    sent = []
    monkeypatch.setattr(contact_service, "send_email", lambda to, subject, body, reply_to=None: sent.append(to) or True)
    shopper.post("/contact", data={"name": "Ada", "email": "ada@example.com", "subject": "Hello there",
                                   "message": "A message long enough."})
    assert sent == ["help@example.com"]

    boss.post("/admin/settings", data=settings_form(announcement_text=""))
    assert b'class="announcement"' not in shopper.get("/").data


@pytest.mark.parametrize("field, value", [
    ("free_shipping_threshold", "abc"), ("standard_shipping_rate", "-1"), ("express_shipping_rate", ""),
    ("tax_rate", "60"), ("tax_rate", "abc"), ("tax_rate", "NaN"), ("tax_rate", "Infinity"),
    ("contact_email", "not-an-email"), ("announcement_text", "x" * 201),
])
def test_invalid_settings_are_rejected(app, seeded, field, value):
    boss = admin(app)
    r = boss.post("/admin/settings", data=settings_form(**{field: value}))
    assert r.status_code == 200
    with app.test_request_context():
        assert pricing_service.calculate(2500)["shipping"] == 599  # still the defaults
