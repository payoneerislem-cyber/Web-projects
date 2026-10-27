"""Order creation. Everything below happens in ONE database transaction:
re-validate the cart, reserve stock, snapshot prices, charge, empty the cart.
Any failure rolls the whole thing back, so no half-created orders and no lost stock."""
import secrets

from flask import current_app, url_for
from sqlalchemy import delete, or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (Address, CartItem, Coupon, CouponUsage, Order, OrderItem, OrderStatus,
                        PaymentStatus, Product)
from app.models.mixins import utcnow
from app.services import coupon_service, payment, pricing_service
from app.services.coupon_service import CouponError
from app.services.email_service import send_email
from app.services.notification_service import notify
from app.utils.money import format_money

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


class CheckoutError(Exception):
    """Something the customer can act on. `needs_cart_fix`: send them back to the cart."""

    def __init__(self, message: str, needs_cart_fix: bool = False):
        super().__init__(message)
        self.needs_cart_fix = needs_cart_fix


class PaymentFailed(CheckoutError):
    """The payment provider refused the payment."""


def _new_order_number() -> str:
    prefix = current_app.config["ORDER_NUMBER_PREFIX"]
    for _ in range(10):
        token = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        number = f"{prefix}-{utcnow():%y%m%d}-{token}"
        if db.session.query(Order.id).filter_by(order_number=number).first() is None:
            return number
    raise CheckoutError("We couldn't generate an order number. Please try again.")


def get_order_for_user(user, order_number: str) -> Order:
    return (Order.query.options(selectinload(Order.items))
            .filter_by(order_number=order_number, user_id=user.id).first_or_404())


def create_order(user, cart, *, customer: dict, address: dict, shipping_method: str,
                 payment_method: str, payment_payload: dict | None = None, notes: str = "",
                 save_address: bool = False) -> Order:
    if cart is None or not cart.items:
        raise CheckoutError("Your cart is empty.", needs_cart_fix=True)
    if shipping_method not in pricing_service.SHIPPING_METHODS:
        raise CheckoutError("Please choose a shipping method.")
    try:
        provider = payment.get_provider(payment_method)
    except KeyError:
        raise CheckoutError("Please choose a payment method.") from None

    try:
        order = _build_and_charge(user, cart, customer, address, shipping_method, provider,
                                  payment_payload or {}, notes, save_address)
        db.session.commit()
    except CheckoutError:
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Order creation failed")
        raise CheckoutError("We couldn't place your order. Nothing was charged. Please try again.") from None

    _send_confirmation_email(order)
    return order


def _build_and_charge(user, cart, customer, address, shipping_method, provider, payload, notes, save_address):
    # 1) Fresh view of the products: prices and stock may have changed since the cart was built.
    ids = [item.product_id for item in cart.items]
    fresh = {p.id: p for p in Product.query.filter(Product.id.in_(ids)).populate_existing().all()}
    max_per_line = current_app.config["MAX_QTY_PER_ITEM"]
    problems = []
    for item in cart.items:
        product = fresh.get(item.product_id)
        if product is None or not product.is_active or product.deleted_at is not None:
            problems.append(f"“{product.name if product else 'An item'}” is no longer available.")
        elif product.stock_quantity < item.quantity:
            left = product.stock_quantity
            problems.append(f"Only {left} of “{product.name}” left in stock." if left > 0
                            else f"“{product.name}” is out of stock.")
        elif item.quantity > max_per_line:
            problems.append(f"You can buy at most {max_per_line} of “{product.name}”.")
    if problems:
        raise CheckoutError(" ".join(problems), needs_cart_fix=True)

    # 2) Totals from the fresh prices
    subtotal = sum(fresh[i.product_id].price * i.quantity for i in cart.items)
    coupon, discount = None, 0
    if cart.coupon_code:
        try:
            coupon = coupon_service.validate(cart.coupon_code, subtotal, user)
        except CouponError as exc:
            raise CheckoutError(f"Coupon {cart.coupon_code} can't be used: {exc}", needs_cart_fix=True) from None
        discount = coupon_service.discount_amount(coupon, subtotal)
    totals = pricing_service.calculate(subtotal, discount=discount, method=shipping_method)

    # 3) The order, with name/price snapshots so later catalogue edits can't change history
    order = Order(
        order_number=_new_order_number(), user_id=user.id,
        customer_name=customer["full_name"], customer_email=customer["email"], customer_phone=customer["phone"],
        status=OrderStatus.PENDING, payment_status=PaymentStatus.PENDING,
        subtotal=totals["subtotal"], discount=totals["discount"], shipping_cost=totals["shipping"],
        tax=totals["tax"], total=totals["total"], shipping_method=shipping_method,
        payment_method=provider.key, shipping_address=address, billing_address=address,
        notes=notes or None, coupon_code=coupon.code if coupon else None,
    )
    for item in cart.items:
        product = fresh[item.product_id]
        order.items.append(OrderItem(
            product_id=product.id, product_name_snapshot=product.name, sku_snapshot=product.sku,
            image_snapshot=product.image_url, price_snapshot=product.price, quantity=item.quantity,
            subtotal=product.price * item.quantity))
    db.session.add(order)

    # 4) Take the cart apart atomically: if a parallel request already ordered it, 0 rows match.
    item_ids = [item.id for item in cart.items]
    removed = db.session.execute(
        delete(CartItem).where(CartItem.cart_id == cart.id, CartItem.id.in_(item_ids))
        .execution_options(synchronize_session=False)).rowcount
    if removed != len(item_ids):
        raise CheckoutError("Your cart changed while ordering. Please review it and try again.", needs_cart_fix=True)
    cart.coupon_code = None

    # 5) Reserve stock with a conditional UPDATE, so two buyers can never oversell the last unit.
    for item in order.items:
        reserved = db.session.execute(
            update(Product)
            .where(Product.id == item.product_id, Product.stock_quantity >= item.quantity,
                   Product.is_active.is_(True), Product.deleted_at.is_(None))
            .values(stock_quantity=Product.stock_quantity - item.quantity,
                    sales_count=Product.sales_count + item.quantity)
            .execution_options(synchronize_session=False)).rowcount
        if reserved != 1:
            raise CheckoutError(f"Sorry, “{item.product_name_snapshot}” just sold out. "
                                "Please review your cart.", needs_cart_fix=True)

    # 5b) Redeem the coupon atomically (usage limit can't be exceeded by parallel orders)
    if coupon is not None:
        redeemed = db.session.execute(
            update(Coupon).where(Coupon.id == coupon.id,
                                 or_(Coupon.usage_limit.is_(None), Coupon.used_count < Coupon.usage_limit))
            .values(used_count=Coupon.used_count + 1).execution_options(synchronize_session=False)).rowcount
        if redeemed != 1:
            raise CheckoutError(f"Sorry, coupon {coupon.code} was just fully redeemed.", needs_cart_fix=True)
        db.session.flush()
        db.session.add(CouponUsage(coupon_id=coupon.id, user_id=user.id, order_id=order.id))

    # 6) Payment (last, so a refusal rolls back everything above)
    result = provider.charge(order, payload)
    if not result.success:
        raise PaymentFailed(result.message or "Your payment could not be processed.")
    order.payment_status = result.status
    order.payment_reference = result.reference
    if result.status == PaymentStatus.PAID:
        order.status = OrderStatus.CONFIRMED

    # 7) Optional: remember a new address
    if save_address:
        has_default = Address.query.filter_by(user_id=user.id, is_default=True).first() is not None
        db.session.add(Address(user_id=user.id, label="Home", is_default=not has_default, **address))

    db.session.flush()
    notify(user.id, "order", "Order placed",
           f"Order {order.order_number} for {format_money(order.total, current_app.config['CURRENCY_SYMBOL'])} was placed.",
           link=url_for("checkout.confirmation", order_number=order.order_number))
    return order


def _send_confirmation_email(order: Order) -> None:
    symbol = current_app.config["CURRENCY_SYMBOL"]
    lines = "\n".join(f"  {i.quantity} x {i.product_name_snapshot}  {format_money(i.subtotal, symbol)}"
                      for i in order.items)
    body = (f"Hi {order.customer_name},\n\nThanks for your order {order.order_number}!\n\n{lines}\n\n"
            f"Total: {format_money(order.total, symbol)}\nPayment: {order.payment_method}\n\n"
            "We'll email you again when it ships.")
    try:
        send_email(order.customer_email, f"Your {current_app.config['STORE_NAME']} order {order.order_number}", body)
    except Exception:  # the order is already saved: never fail checkout over an email
        current_app.logger.exception("Could not send the order confirmation email")
