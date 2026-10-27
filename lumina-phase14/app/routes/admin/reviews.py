"""Admin: review moderation."""
from flask import flash, render_template, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Product, Review, ReviewStatus, User
from app.routes.admin import bp
from app.routes.admin._helpers import back, like, paginate, pagination_args
from app.services import review_service


@bp.get("/reviews")
def reviews():
    q = " ".join((request.args.get("q") or "").split())[:100]
    status = request.args.get("status", "")
    query = Review.query.options(joinedload(Review.user), joinedload(Review.product))
    if status in ReviewStatus.ALL:
        query = query.filter(Review.status == status)
    if q:
        pattern = like(q)
        query = (query.join(Product, Product.id == Review.product_id).join(User, User.id == Review.user_id)
                 .filter(or_(Product.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\"),
                             Review.content.ilike(pattern, escape="\\"))))
    pagination = paginate(query.order_by(Review.created_at.desc(), Review.id.desc()))
    return render_template("admin/reviews.html", reviews=pagination, q=q, status=status,
                           statuses=ReviewStatus.ALL, args=pagination_args())


@bp.post("/reviews/<int:review_id>/status")
def review_status(review_id):
    review = db.get_or_404(Review, review_id)
    new_status = request.form.get("status", "")
    if new_status not in ReviewStatus.ALL:
        flash("Unknown status.", "error")
    else:
        review.status = new_status
        db.session.flush()
        review_service.recalculate(review.product_id)  # hidden reviews stop counting
        db.session.commit()
        flash(f"Review {new_status}.", "success")
    return back("admin.reviews")


@bp.post("/reviews/<int:review_id>/delete")
def review_delete(review_id):
    review = db.get_or_404(Review, review_id)
    product_id = review.product_id
    db.session.delete(review)
    db.session.flush()
    review_service.recalculate(product_id)
    db.session.commit()
    flash("Review deleted.", "info")
    return back("admin.reviews")
