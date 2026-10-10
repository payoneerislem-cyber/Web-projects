from app.extensions import db
from app.models.mixins import TimestampMixin


class OrderStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    ALL = (PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED, REFUNDED)

    # Allowed admin transitions
    TRANSITIONS = {
        PENDING: (CONFIRMED, CANCELLED),
        CONFIRMED: (PROCESSING, CANCELLED),
        PROCESSING: (SHIPPED, CANCELLED),
        SHIPPED: (DELIVERED,),
        DELIVERED: (REFUNDED,),
        CANCELLED: (),
        REFUNDED: (),
    }
    # Statuses where stock goes back to inventory
    RESTOCK_ON = (CANCELLED, REFUNDED)


class PaymentStatus:
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    ALL = (PENDING, PAID, FAILED, REFUNDED)


def _in_list(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint(_in_list("status", OrderStatus.ALL), name="status_valid"),
        db.CheckConstraint(_in_list("payment_status", PaymentStatus.ALL), name="payment_status_valid"),
        db.CheckConstraint("total >= 0", name="total_non_negative"),
        db.Index("ix_orders_user_created", "user_id", "created_at"),
        db.Index("ix_orders_status", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    # Customer snapshot (kept even if the account is later deleted)
    customer_name = db.Column(db.String(120))
    customer_email = db.Column(db.String(255))
    customer_phone = db.Column(db.String(30))

    status = db.Column(db.String(20), nullable=False, default=OrderStatus.PENDING)
    payment_status = db.Column(db.String(20), nullable=False, default=PaymentStatus.PENDING)

    # Money in integer cents
    subtotal = db.Column(db.Integer, nullable=False, default=0)
    discount = db.Column(db.Integer, nullable=False, default=0)
    shipping_cost = db.Column(db.Integer, nullable=False, default=0)
    tax = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)

    coupon_code = db.Column(db.String(50))
    shipping_method = db.Column(db.String(50))
    payment_method = db.Column(db.String(50), nullable=False, default="cod")
    payment_reference = db.Column(db.String(100))
    shipping_address = db.Column(db.JSON, nullable=False)  # immutable snapshot
    billing_address = db.Column(db.JSON)
    notes = db.Column(db.Text)

    user = db.relationship("User", back_populates="orders")
    items = db.relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan",
        passive_deletes=True, order_by="OrderItem.id",
    )

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in OrderStatus.TRANSITIONS.get(self.status, ())

    @property
    def is_cancellable_by_customer(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.CONFIRMED)

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)

    def __repr__(self) -> str:
        return f"<Order {self.order_number}>"


class OrderItem(db.Model):
    """Line item with snapshots: survives product edits/deletion."""

    __tablename__ = "order_items"
    __table_args__ = (db.CheckConstraint("quantity > 0", name="quantity_positive"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    product_name_snapshot = db.Column(db.String(200), nullable=False)
    sku_snapshot = db.Column(db.String(64))
    image_snapshot = db.Column(db.String(500))
    price_snapshot = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")
