"""Load demo data (admin, customer, categories, products, reviews, coupons).

    python seed.py            # seed an empty database
    python seed.py --reset    # wipe all data first, then seed

Demo logins (also listed in README):
    admin@example.com    / Admin12345
    customer@example.com / Customer12345
Override with SEED_ADMIN_PASSWORD / SEED_CUSTOMER_PASSWORD in .env.
"""
import os
import random
import sys
from datetime import timedelta
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import (Address, Category, Coupon, Product, ProductImage, Review,
                        Role, User)
from app.models.mixins import utcnow
from app.utils.money import to_cents
from app.utils.placeholders import artwork_svg
from app.utils.slugs import slugify

ADMIN_EMAIL = "admin@example.com"
CUSTOMER_EMAIL = "customer@example.com"
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "Admin12345")
CUSTOMER_PASSWORD = os.environ.get("SEED_CUSTOMER_PASSWORD", "Customer12345")


class SeedError(Exception):
    pass


# (name, brand, price, compare_at_price, short description)
CATEGORIES = [
    dict(name="Audio", code="AUD", glyph="headphones", hue=250,
         description="Headphones, earbuds and speakers for every mood.",
         specs={"Connectivity": "Bluetooth 5.3", "Battery life": "Up to 30 hours"},
         products=[
             ("Aurora Wireless Headphones", "Sonic", 149, 199, "Over-ear noise-cancelling headphones with a 30-hour battery."),
             ("Pulse Earbuds Pro", "Sonic", 89, None, "True wireless earbuds with active noise cancelling."),
             ("Echo Studio Speaker", "Resona", 129, 159, "Room-filling smart speaker with deep, clear sound."),
             ("Bassline Portable Speaker", "Resona", 59, None, "Waterproof pocket speaker with 12 hours of playtime."),
             ("Studio Monitor Headset", "Sonic", 199, 249, "Reference-grade wired headset for creators."),
         ]),
    dict(name="Wearables", code="WEA", glyph="watch", hue=160,
         description="Smart watches and trackers that keep up with you.",
         specs={"Water resistance": "5 ATM", "Battery life": "Up to 7 days"},
         products=[
             ("Nova Smart Watch", "Orbit", 249, None, "AMOLED smart watch with GPS and health tracking."),
             ("Pulse Fitness Band", "Orbit", 59, 79, "Slim fitness band with heart-rate and sleep tracking."),
             ("Halo Ring Tracker", "Orbit", 199, None, "Discreet smart ring for sleep and recovery insights."),
             ("Aero Sport Watch", "Kinetic", 179, 219, "Rugged multisport watch with offline maps."),
             ("Kids Tracker Watch", "Kinetic", 69, None, "Colourful, durable watch with safe-zone alerts."),
         ]),
    dict(name="Cameras", code="CAM", glyph="camera", hue=20,
         description="Cameras and gear for capturing every moment.",
         specs={"Video": "4K / 60 fps", "Storage": "microSD / SD"},
         products=[
             ("Vista Mirrorless Camera", "Lenzo", 899, 999, "24 MP mirrorless camera with fast autofocus."),
             ("Snap Instant Camera", "Lenzo", 79, None, "Retro instant camera that prints in seconds."),
             ("Action Cam 4K", "Kinetic", 169, 199, "Waterproof action camera with stabilised 4K video."),
             ("Pocket Gimbal", "Lenzo", 119, None, "Foldable 3-axis gimbal for smooth handheld shots."),
             ("Tripod Pro", "Lenzo", 49, None, "Lightweight aluminium tripod with a quick-release plate."),
         ]),
    dict(name="Home & Kitchen", code="HOM", glyph="coffee", hue=35,
         description="Small appliances and everyday essentials for the home.",
         specs={"Power": "1200 W", "Cleaning": "Dishwasher-safe parts"},
         products=[
             ("Brew Master Coffee Maker", "Hearth", 129, 159, "Programmable coffee maker with a built-in grinder."),
             ("Terra Steel Bottle", "Terra", 29, None, "Insulated bottle that keeps drinks cold for 24 hours."),
             ("Ember Electric Kettle", "Hearth", 49, None, "Fast-boil kettle with temperature presets."),
             ("Chef Series Blender", "Hearth", 99, 129, "High-speed blender for smoothies, soups and sauces."),
             ("Aroma Diffuser", "Terra", 39, None, "Ultrasonic diffuser with a soft ambient light."),
         ]),
    dict(name="Computing", code="COM", glyph="monitor", hue=210,
         description="Laptops, displays and desk upgrades.",
         specs={"Warranty": "2 years", "Ports": "USB-C / HDMI"},
         products=[
             ("Slate Ultrabook 14", "Vertex", 1099, 1299, "Thin and light 14-inch laptop with all-day battery."),
             ("Pixel Monitor 27", "Vertex", 329, None, "27-inch 4K IPS monitor with USB-C charging."),
             ("Keystone Mechanical Keyboard", "Keystone", 119, 149, "Hot-swappable mechanical keyboard with backlighting."),
             ("Glide Wireless Mouse", "Keystone", 49, None, "Ergonomic wireless mouse with silent clicks."),
             ("USB-C Hub 8-in-1", "Vertex", 59, None, "Adds HDMI, Ethernet, SD and extra USB ports."),
         ]),
    dict(name="Accessories", code="ACC", glyph="bag", hue=320,
         description="Bags, chargers and everyday carry.",
         specs={"Material": "Recycled fabric", "Care": "Wipe clean"},
         products=[
             ("Voyager Backpack", "Atlas", 89, 119, "Water-resistant backpack with a padded laptop sleeve."),
             ("Leather Card Wallet", "Atlas", 39, None, "Slim wallet in full-grain leather with RFID shielding."),
             ("Charge Stand 3-in-1", "Volt", 69, None, "Charges phone, watch and earbuds from one stand."),
             ("Power Bank 20000mAh", "Volt", 45, 59, "High-capacity power bank with fast charging."),
             ("Phone Case Shield", "Atlas", 25, None, "Drop-protection case with a raised camera edge."),
         ]),
]

STOCK_BY_POSITION = [30, 45, 12, 4, 18]  # position 3 -> low stock
OUT_OF_STOCK = {"Tripod Pro"}

REVIEWERS = [("Alice Morgan", "alice@example.com"), ("Omar Khalid", "omar@example.com"),
             ("Sara Lopez", "sara@example.com"), ("Liam Brown", "liam@example.com"),
             ("Noor Hassan", "noor@example.com"), ("Chen Wei", "chen@example.com")]

POSITIVE = [("Great value for money", "The quality is better than I expected at this price."),
            ("Exactly what I needed", "Arrived quickly and works exactly as described."),
            ("Love it", "Looks great and feels well made. Very happy with the purchase."),
            ("Would buy again", "Packaging was lovely and the product feels premium.")]
NEUTRAL = [("Good, but not perfect", "Decent product overall with a few small niggles."),
           ("It's okay", "Works fine, nothing special for the price.")]
NEGATIVE = [("Not what I hoped", "Didn't quite meet my expectations."),
            ("Disappointing", "Had some issues out of the box.")]


def _wipe() -> None:
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_database(*, reset: bool = False, write_images: bool = True) -> dict:
    """Populate the database. Must run inside an app context."""
    from flask import current_app

    if reset:
        _wipe()
    elif Category.query.first() or User.query.first():
        raise SeedError("The database already has data. Run `python seed.py --reset` to wipe and re-seed.")

    rng = random.Random(42)
    now = utcnow()
    images_dir = Path(current_app.static_folder) / "images"

    # --- users ---
    admin = User(email=ADMIN_EMAIL, name="Store Admin", role=Role.ADMIN)
    admin.set_password(ADMIN_PASSWORD)
    customer = User(email=CUSTOMER_EMAIL, name="Demo Customer")
    customer.set_password(CUSTOMER_PASSWORD)
    reviewers = []
    for name, email in REVIEWERS:
        user = User(email=email, name=name)
        user.password_hash = "!"  # unusable hash: demo shoppers can never log in
        reviewers.append(user)
    db.session.add_all([admin, customer, *reviewers])
    db.session.flush()
    db.session.add(Address(user_id=customer.id, label="Home", full_name="Demo Customer",
                           phone="+1 555 0100", line1="12 Market Street", city="Springfield",
                           state="IL", postal_code="62701", country="United States",
                           is_default=True))

    # --- catalogue ---
    product_count = review_count = 0
    for cat_data in CATEGORIES:
        slug = slugify(cat_data["name"])
        category = Category(name=cat_data["name"], slug=slug, description=cat_data["description"],
                            image=f"/static/images/categories/{slug}.svg")
        db.session.add(category)
        db.session.flush()
        if write_images:
            _write(images_dir / "categories" / f"{slug}.svg",
                   artwork_svg(cat_data["glyph"], cat_data["hue"], 1))

        for position, (name, brand, price, compare, short) in enumerate(cat_data["products"]):
            p_slug = slugify(name)
            is_best = position in (0, 2)
            is_new = position in (3, 4)
            product = Product(
                name=name, slug=p_slug, sku=f"LUM-{cat_data['code']}-{position + 1:03d}",
                brand=brand, category_id=category.id, short_description=short,
                description=(f"{short}\n\nDesigned for everyday use and built to last. "
                             "Every order is covered by our 30-day return policy."),
                specs={"Brand": brand, **cat_data["specs"], "Warranty": "1 year"},
                price=to_cents(price), compare_at_price=to_cents(compare) if compare else None,
                cost_price=int(to_cents(price) * 0.6),
                stock_quantity=0 if name in OUT_OF_STOCK else STOCK_BY_POSITION[position],
                low_stock_threshold=5, main_image=f"/static/images/products/{p_slug}-1.svg",
                is_featured=position in (0, 1), is_new=is_new, is_best_seller=is_best,
                sales_count=rng.randint(150, 600) if is_best else rng.randint(5, 150),
                created_at=now - timedelta(days=rng.randint(1, 10) if is_new else rng.randint(20, 90)),
            )
            for n in (1, 2, 3):
                product.images.append(ProductImage(
                    url=f"/static/images/products/{p_slug}-{n}.svg",
                    alt=f"{name}, view {n}", position=n - 1))
                if write_images:
                    _write(images_dir / "products" / f"{p_slug}-{n}.svg",
                           artwork_svg(cat_data["glyph"], cat_data["hue"] + (n - 1) * 28, n))
            db.session.add(product)
            db.session.flush()
            product_count += 1

            # --- reviews (about 1 in 10 products has none) ---
            wanted = 0 if rng.random() < 0.1 else rng.randint(2, 5)
            ratings = []
            for user in rng.sample(reviewers, wanted):
                rating = rng.choices([5, 4, 3, 2, 1], weights=[45, 30, 15, 7, 3])[0]
                pool = POSITIVE if rating >= 4 else NEUTRAL if rating == 3 else NEGATIVE
                title, content = rng.choice(pool)
                db.session.add(Review(user_id=user.id, product_id=product.id, rating=rating,
                                      title=title, content=content,
                                      created_at=now - timedelta(days=rng.randint(1, 30))))
                ratings.append(rating)
            product.review_count = len(ratings)
            product.avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
            review_count += len(ratings)

    # --- coupons ---
    db.session.add_all([
        Coupon(code="WELCOME10", description="10% off your first order", discount_type="percentage",
               discount_value=10, minimum_order=0, per_user_limit=1,
               expiry_date=now + timedelta(days=365)),
        Coupon(code="SAVE5", description="$5 off orders over $25", discount_type="fixed",
               discount_value=500, minimum_order=2500, per_user_limit=3,
               expiry_date=now + timedelta(days=365)),
        Coupon(code="BIG25", description="25% off orders over $200 (max $50)", discount_type="percentage",
               discount_value=25, minimum_order=20000, maximum_discount=5000, usage_limit=100,
               expiry_date=now + timedelta(days=90)),
        Coupon(code="EXPIRED20", description="Expired coupon for testing", discount_type="percentage",
               discount_value=20, expiry_date=now - timedelta(days=10)),
    ])
    db.session.commit()
    return {"users": 2 + len(reviewers), "categories": len(CATEGORIES),
            "products": product_count, "reviews": review_count, "coupons": 4}


def main() -> None:
    app = create_app()
    if app.config["ENV_NAME"] == "production":
        sys.exit("Seeding is disabled in production.")
    with app.app_context():
        try:
            summary = seed_database(reset="--reset" in sys.argv)
        except SeedError as exc:
            sys.exit(str(exc))
    print("Seeded:", ", ".join(f"{v} {k}" for k, v in summary.items()))
    print(f"Admin:    {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"Customer: {CUSTOMER_EMAIL} / {CUSTOMER_PASSWORD}")
    print("Coupons:  WELCOME10, SAVE5, BIG25 (EXPIRED20 is expired on purpose)")


if __name__ == "__main__":
    main()
