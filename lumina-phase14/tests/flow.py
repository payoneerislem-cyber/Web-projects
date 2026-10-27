"""Shared helpers for the shopping-flow tests (phases 10-14)."""
import io

from PIL import Image

from app.models import Order, Product

CUSTOMER = ("customer@example.com", "Customer12345")
ADMIN = ("admin@example.com", "Admin12345")
AURORA = "aurora-wireless-headphones"
BASSLINE = "bassline-portable-speaker"
CASE = "phone-case-shield"
TRIPOD = "tripod-pro"


def product(slug):
    return Product.query.filter_by(slug=slug).one()


def login(client, creds=CUSTOMER):
    return client.post("/login", data={"email": creds[0], "password": creds[1]})


def add_to_cart(client, slug, quantity=1):
    return client.post("/api/cart/add", json={"product_id": product(slug).id, "quantity": quantity})


def checkout_data(**overrides):
    data = {
        "full_name": "Demo Customer", "email": "customer@example.com", "phone": "+1 555 0100",
        "address_id": "new", "line1": "1 Test Street", "line2": "", "city": "Testville", "state": "TS",
        "postal_code": "12345", "country": "United States", "shipping_method": "standard",
        "payment_method": "cod", "demo_scenario": "approve", "notes": "", "accept_terms": "y",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def place_order(client, items=((AURORA, 1),), creds=CUSTOMER, coupon=None, **overrides):
    """Log in, fill the cart, optionally apply a coupon, check out. Returns the new Order."""
    login(client, creds)
    for slug, quantity in items:
        response = add_to_cart(client, slug, quantity)
        assert response.status_code == 200, response.get_json()
    if coupon:
        response = client.post("/api/cart/coupon", json={"code": coupon})
        assert response.status_code == 200, response.get_json()
    response = client.post("/checkout", data=checkout_data(**overrides))
    assert response.status_code == 302 and "confirmation" in response.headers["Location"], response.data[:400]
    return Order.query.order_by(Order.id.desc()).first()


def png_bytes(size=(24, 24), color=(200, 40, 40)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()
