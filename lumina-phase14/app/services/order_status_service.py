"""Order lifecycle: status changes, restocking, refunds and customer notifications."""
from flask import url_for
from sqlalchemy import case, update
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import OrderStatus, PaymentStatus, Product
from app.services import coupon_service, payment
from app.services.notification_service import notify

MESSAGES = {
    OrderStatus.CONFIRMED: ("Order confirmed", "Your order {n} has been confirmed."),
    OrderStatus.PROCESSING: ("Order is being prepared", "We're preparing order {n}."),
    OrderStatus.SHIPPED: ("Order shipped", "Good news! Order {n} is on its way."),
    OrderStatus.DELIVERED: ("Order delivered", "Order {n} was delivered. You can now review the items you bought."),
    OrderStatus.CANCELLED: ("Order cancelled", "Order {n} was cancelled."),
    OrderStatus.REFUNDED: ("Order refunded", "Order {n} was refunded."),
}


class OrderError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _restock(order) -> None:
    for item in order.items:
        if item.product_id is None:  # product was deleted: nothing to restock
            continue
        db.session.execute(
            update(Product).where(Product.id == item.product_id)
            .values(stock_quantity=Product.stock_quantity + item.quantity,
                    sales_count=case((Product.sales_count >= item.quantity, Product.sales_count - item.quantity), else_=0))
            .execution_options(synchronize_session=False))


def change_status(order, new_status: str, *, by_customer: bool = False) -> None:
    """Move an order to `new_status`, applying every side effect in one transaction."""
    if new_status not in OrderStatus.ALL:
        raise OrderError("Unknown order status.")
    if by_customer and (new_status != OrderStatus.CANCELLED or not order.is_cancellable_by_customer):
        raise OrderError("This order can no longer be cancelled online. Please contact support.", 403)
    if not order.can_transition_to(new_status):
        raise OrderError(f"An order that is {order.status} can't become {new_status}.", 409)

    try:
        if new_status in OrderStatus.RESTOCK_ON:
            _restock(order)
            coupon_service.release(order)
        if new_status == OrderStatus.DELIVERED and order.payment_method == "cod" \
                and order.payment_status == PaymentStatus.PENDING:
            order.payment_status = PaymentStatus.PAID  # cash collected on delivery
        if new_status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED) \
                and order.payment_status == PaymentStatus.PAID:
            try:
                result = payment.get_provider(order.payment_method).refund(order)
                order.payment_reference = result.reference or order.payment_reference
            except KeyError:
                pass
            order.payment_status = PaymentStatus.REFUNDED
        order.status = new_status
        if order.user_id and new_status in MESSAGES:
            title, text = MESSAGES[new_status]
            notify(order.user_id, "order", title, text.format(n=order.order_number),
                   link=url_for("account.order_detail", order_number=order.order_number))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise OrderError("Couldn't update the order. Please try again.", 500) from None
