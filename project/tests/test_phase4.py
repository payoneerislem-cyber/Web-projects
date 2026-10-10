import re

import pytest

from app.extensions import db
from app.models import Cart, CartItem, Category, Product, User
from app.utils.context import asset, safe_url

PASSWORD = "Secret123!"

ASSETS = [
    "css/tokens.css", "css/base.css", "css/components.css", "css/pages.css",
    "js/theme-init.js", "js/main.js", "js/ui.js", "js/api.js", "js/search.js", "js/filters.js", "js/product.js", "js/cart.js", "images/favicon.svg",
]


def make_user(email="user@example.com", name="Test User"):
    user = User(email=email, name=name)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email="user@example.com"):
    return client.post("/login", data={"email": email, "password": PASSWORD})


def test_base_layout_elements(client):
    html = client.get("/").data
    for marker in (b'class="skip-link"', b'id="site-header"', b'id="mobile-drawer"',
                   b'id="toast-region"', b'name="csrf-token"', b"theme-init.js",
                   b'type="module"', b"site-footer", b"announcement"):
        assert marker in html, marker


def test_static_assets_served(client):
    for path in ASSETS:
        assert client.get(f"/static/{path}").status_code == 200, path


def test_no_inline_styles_or_scripts_in_layout(client):
    """CSP forbids them, so the layout must not rely on them."""
    html = client.get("/").data.decode()
    assert ' style="' not in html
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)


def test_badges_for_logged_in_user(client):
    user = make_user()
    cat = Category(name="Audio", slug="audio")
    db.session.add(cat)
    db.session.flush()
    p1 = Product(name="A", slug="a", sku="A", price=100, category_id=cat.id)
    p2 = Product(name="B", slug="b", sku="B", price=100, category_id=cat.id)
    cart = Cart(user_id=user.id)
    db.session.add_all([p1, p2, cart])
    db.session.flush()
    cart.items.extend([CartItem(product_id=p1.id, quantity=1), CartItem(product_id=p2.id, quantity=2)])
    db.session.commit()

    login(client)
    html = client.get("/").data
    assert re.search(rb'data-badge="cart">\s*3\s*<', html)
    assert b'data-badge="wishlist" hidden' in html


def test_badges_hidden_for_guest(client):
    html = client.get("/").data
    assert b'data-badge="cart" hidden' in html


def test_nav_lists_only_active_categories(client):
    db.session.add_all([
        Category(name="Audio", slug="audio", is_active=True),
        Category(name="Secret", slug="secret", is_active=False),
    ])
    db.session.commit()
    html = client.get("/").data
    assert b">Audio<" in html
    assert b"Secret" not in html


def test_user_name_is_escaped_in_header(client):
    make_user(name="<script>alert(1)</script>")
    login(client)
    html = client.get("/").data
    assert b"<script>alert(1)</script>" not in html
    assert b"&lt;script&gt;" in html


def test_flash_rendered_as_toast(client):
    r = client.post("/login", data={"email": "no@example.com", "password": "x"})
    assert b"toast toast-error" in r.data
    assert b"Invalid email or password." in r.data


def test_error_page_uses_layout(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert b"site-header" in r.data and b"error-code" in r.data


def test_styleguide_only_in_dev(app, client):
    r = client.get("/styleguide")
    assert r.status_code == 200
    assert b"product-card" in r.data and b"Aurora Wireless Headphones" in r.data
    app.testing = False  # simulate production-like mode
    try:
        assert client.get("/styleguide").status_code == 404
    finally:
        app.testing = True


def test_safe_url_fallback_and_asset(app):
    with app.test_request_context("/"):
        assert safe_url("main.index") == "/"
        assert safe_url("shop.does_not_exist", "/shop") == "/shop"
        assert asset("css/tokens.css").startswith("/static/css/tokens.css?v=")
