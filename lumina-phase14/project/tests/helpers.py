"""Small factories shared by tests."""
import itertools

from app.extensions import db
from app.models import Category, Product, User

_counter = itertools.count(1)


def make_user(**kwargs) -> User:
    n = next(_counter)
    data = {"email": f"user{n}@example.com", "name": f"User {n}"}
    data.update(kwargs)
    password = data.pop("password", "Passw0rd!x")
    user = User(**data)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def make_category(**kwargs) -> Category:
    n = next(_counter)
    data = {"name": f"Category {n}", "slug": f"category-{n}"}
    data.update(kwargs)
    category = Category(**data)
    db.session.add(category)
    db.session.commit()
    return category


def make_product(**kwargs) -> Product:
    n = next(_counter)
    data = {
        "name": "Test Product", "slug": f"test-product-{n}", "sku": f"SKU-{n}",
        "price": 1000, "stock_quantity": 10,
    }
    if "category_id" not in data and "category" not in kwargs:
        data["category_id"] = make_category().id
    data.update(kwargs)
    product = Product(**data)
    db.session.add(product)
    db.session.commit()
    return product
