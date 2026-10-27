"""Admin: orders and their lifecycle."""
from flask import flash, render_template, request
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Order, OrderStatus
from app.routes.admin import bp
from app.routes.admin._helpers import back, like, paginate, pagination_args
from app.services import order_status_service, payment, pricing_service
from app.services.order_status_service import OrderError


@bp.get("/orders")
def orders():
    q = " ".join((request.args.get("q") or "").split())[:100]
    status = request.args.get("status", "")
    query = Order.query.options(selectinload(Order.items))
    if status in OrderStatus.ALL:
        query = query.filter(Order.status == status)
    if q:
        pattern = like(q)
        query = query.filter(or_(Order.order_number.ilike(pattern, escape="\\"), Order.customer_email.ilike(pattern, escape="\\"),
                                 Order.customer_name.ilike(pattern, escape="\\")))
    pagination = paginate(query.order_by(Order.created_at.desc(), Order.id.desc()))
    return render_template("admin/orders.html", orders=pagination, q=q, status=status,
                           statuses=OrderStatus.ALL, args=pagination_args())


@bp.get("/orders/<int:order_id>")
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    try:
        payment_label = payment.get_provider(order.payment_method).label
    except KeyError:
        payment_label = order.payment_method
    method = pricing_service.SHIPPING_METHODS.get(order.shipping_method, {})
    return render_template("admin/order_detail.html", order=order, payment_label=payment_label,
                           shipping_label=method.get("label", order.shipping_method),
                           next_statuses=OrderStatus.TRANSITIONS.get(order.status, ()))


@bp.post("/orders/<int:order_id>/status")
def order_status(order_id):
    order = db.get_or_404(Order, order_id)
    try:
        order_status_service.change_status(order, request.form.get("status", ""))
        flash(f"Order {order.order_number} is now {order.status}.", "success")
    except OrderError as exc:
        flash(str(exc), "error")
    return back("admin.order_detail", order_id=order_id)
