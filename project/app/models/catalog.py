from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    image = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # RESTRICT at DB level: a category that still has products can't be deleted.
    products = db.relationship("Product", back_populates="category", passive_deletes=True)

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("price >= 0", name="price_non_negative"),
        db.CheckConstraint("stock_quantity >= 0", name="stock_non_negative"),
        db.Index("ix_products_category_active", "category_id", "is_active"),
        db.Index("ix_products_price", "price"),
        db.Index("ix_products_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), nullable=False, unique=True, index=True)
    sku = db.Column(db.String(64), nullable=False, unique=True, index=True)
    short_description = db.Column(db.String(300))
    description = db.Column(db.Text)
    specs = db.Column(db.JSON)  # e.g. {"Color": "Black", "Weight": "250g"}

    # Money in integer cents
    price = db.Column(db.Integer, nullable=False)
    compare_at_price = db.Column(db.Integer)
    cost_price = db.Column(db.Integer, nullable=False, default=0)

    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)

    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    brand = db.Column(db.String(80), index=True)
    main_image = db.Column(db.String(500))

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    is_new = db.Column(db.Boolean, nullable=False, default=False)
    is_best_seller = db.Column(db.Boolean, nullable=False, default=False)

    # Denormalised counters (kept up to date by services)
    avg_rating = db.Column(db.Float, nullable=False, default=0.0)
    review_count = db.Column(db.Integer, nullable=False, default=0)
    sales_count = db.Column(db.Integer, nullable=False, default=0)

    deleted_at = db.Column(db.DateTime)  # soft delete

    category = db.relationship("Category", back_populates="products")
    images = db.relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan",
        passive_deletes=True, order_by="ProductImage.position",
    )
    reviews = db.relationship(
        "Review", back_populates="product", cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- querying ---
    @classmethod
    def visible_query(cls):
        """Products customers may see: active and not soft-deleted."""
        return cls.query.filter(cls.is_active.is_(True), cls.deleted_at.is_(None))

    # --- computed properties ---
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_available(self) -> bool:
        return self.is_active and not self.is_deleted and self.stock_quantity > 0

    @property
    def stock_status(self) -> str:
        if self.stock_quantity <= 0:
            return "out_of_stock"
        if self.stock_quantity <= self.low_stock_threshold:
            return "low_stock"
        return "in_stock"

    @property
    def discount_percent(self) -> int:
        if self.compare_at_price and self.compare_at_price > self.price:
            return round((1 - self.price / self.compare_at_price) * 100)
        return 0

    @property
    def image_url(self):
        if self.main_image:
            return self.main_image
        return self.images[0].url if self.images else None

    def __repr__(self) -> str:
        return f"<Product {self.sku}>"


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url = db.Column(db.String(500), nullable=False)  # URL or /static/... path
    alt = db.Column(db.String(200))
    position = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship("Product", back_populates="images")
