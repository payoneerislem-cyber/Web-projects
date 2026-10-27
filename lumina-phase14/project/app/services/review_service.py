"""Product reviews: verified-purchase check, create/update/delete, rating totals."""
from sqlalchemy import func

from app.extensions import db
from app.models import Order, OrderItem, OrderStatus, Product, Review, ReviewStatus


def has_purchased(user, product_id: int) -> bool:
    """True once an order containing the product has been delivered to this user."""
    return (db.session.query(OrderItem.id).join(Order, Order.id == OrderItem.order_id)
            .filter(Order.user_id == user.id, OrderItem.product_id == product_id,
                    Order.status == OrderStatus.DELIVERED).first() is not None)


def get_user_review(user, product_id: int):
    return Review.query.filter_by(user_id=user.id, product_id=product_id).first()


def recalculate(product_id: int) -> None:
    """Refresh the product's cached rating from its approved reviews (no commit)."""
    count, average = (db.session.query(func.count(Review.id), func.avg(Review.rating))
                      .filter(Review.product_id == product_id, Review.status == ReviewStatus.APPROVED).one())
    product = db.session.get(Product, product_id)
    if product is not None:
        product.review_count = count or 0
        product.avg_rating = round(float(average), 1) if average else 0.0


def save_review(user, product, rating: int, title: str | None, content: str | None) -> Review:
    review = get_user_review(user, product.id)
    if review is None:
        review = Review(user_id=user.id, product_id=product.id, is_verified_purchase=True)
        db.session.add(review)
    review.rating = rating
    review.title = (title or "").strip() or None
    review.content = (content or "").strip() or None
    db.session.flush()
    recalculate(product.id)
    db.session.commit()
    return review


def delete_review(user, product) -> bool:
    review = get_user_review(user, product.id)
    if review is None:
        return False
    db.session.delete(review)
    db.session.flush()
    recalculate(product.id)
    db.session.commit()
    return True
