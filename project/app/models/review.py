from app.extensions import db
from app.models.mixins import TimestampMixin


class ReviewStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ALL = (PENDING, APPROVED, REJECTED)


class Review(TimestampMixin, db.Model):
    __tablename__ = "reviews"
    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_reviews_user_product"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="rating_range"),
        db.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="status_valid"),
        db.Index("ix_reviews_product_status", "product_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(150))
    content = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default=ReviewStatus.APPROVED)
    is_verified_purchase = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="reviews")
    product = db.relationship("Product", back_populates="reviews")
