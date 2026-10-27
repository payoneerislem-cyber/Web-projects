"""Customer account area. Every route requires login (enforced in before_request)."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db, limiter
from app.forms.account import AddressForm, ChangePasswordForm, ProfileForm
from app.models import Address, Notification, Order
from app.services import (auth_service, order_service, order_status_service, payment, pricing_service,
                          wishlist_service)
from app.services.order_status_service import OrderError

bp = Blueprint("account", __name__, url_prefix="/account")

ADDRESS_FIELDS = ("label", "full_name", "phone", "line1", "line2", "city", "state", "postal_code", "country")
OPTIONAL_ADDRESS_FIELDS = {"label", "line2", "state"}


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    return None


def _my_orders():
    return (Order.query.options(selectinload(Order.items)).filter_by(user_id=current_user.id)
            .order_by(Order.created_at.desc(), Order.id.desc()))


def _page() -> int:
    return max(request.args.get("page", 1, type=int), 1)


# ------------------------------------------------------------------ overview
@bp.get("")
def dashboard():
    stats = {
        "orders": Order.query.filter_by(user_id=current_user.id).count(),
        "wishlist": len(wishlist_service.product_ids(current_user)),
        "unread": db.session.query(func.count(Notification.id))
                  .filter_by(user_id=current_user.id, is_read=False).scalar() or 0,
    }
    return render_template("account/dashboard.html", recent=_my_orders().limit(3).all(), stats=stats)


# ------------------------------------------------------------------ orders
@bp.get("/orders")
def orders():
    page = _page()
    pagination = _my_orders().paginate(page=page, per_page=10, error_out=False)
    if pagination.pages and page > pagination.pages:
        return redirect(url_for("account.orders", page=pagination.pages))
    return render_template("account/orders.html", orders=pagination)


@bp.get("/orders/<order_number>")
def order_detail(order_number):
    order = order_service.get_order_for_user(current_user, order_number)
    try:
        payment_label = payment.get_provider(order.payment_method).label
    except KeyError:
        payment_label = order.payment_method
    method = pricing_service.SHIPPING_METHODS.get(order.shipping_method, {})
    return render_template("account/order_detail.html", order=order, payment_label=payment_label,
                           shipping_label=method.get("label", order.shipping_method), shipping_eta=method.get("eta", ""))


@bp.post("/orders/<order_number>/cancel")
def order_cancel(order_number):
    order = order_service.get_order_for_user(current_user, order_number)
    try:
        order_status_service.change_status(order, "cancelled", by_customer=True)
        flash("Your order was cancelled.", "success")
    except OrderError as exc:
        flash(str(exc), "error")
    return redirect(url_for("account.order_detail", order_number=order_number))


# ------------------------------------------------------------------ wishlist
@bp.get("/wishlist")
def wishlist():
    return render_template("account/wishlist.html", products=wishlist_service.list_products(current_user))


# ------------------------------------------------------------------ profile
@bp.get("/profile")
def profile():
    return render_template("account/profile.html")


@bp.route("/profile/edit", methods=["GET", "POST"])
def profile_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.phone = form.phone.data or None
        db.session.commit()
        flash("Your profile was updated.", "success")
        return redirect(url_for("account.profile"))
    return render_template("account/profile_edit.html", form=form)


@bp.route("/password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors = [*form.current_password.errors, "Your current password is incorrect."]
        else:
            auth_service.reset_password(current_user._get_current_object(), form.new_password.data)
            flash("Your password was changed.", "success")
            return redirect(url_for("account.profile"))
    return render_template("account/password.html", form=form)


# ------------------------------------------------------------------ addresses
def _own_address(address_id: int) -> Address:
    return Address.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()


def _save_address(form, address: Address | None = None) -> Address:
    is_new = address is None
    address = address or Address(user_id=current_user.id)
    for name in ADDRESS_FIELDS:
        value = getattr(form, name).data
        setattr(address, name, (value or None) if name in OPTIONAL_ADDRESS_FIELDS else value)
    first_ever = is_new and Address.query.filter_by(user_id=current_user.id).count() == 0
    if form.is_default.data or first_ever:
        Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
        address.is_default = True
    db.session.add(address)
    db.session.commit()
    return address


@bp.route("/addresses", methods=["GET", "POST"])
def addresses():
    form = AddressForm()
    if request.method == "GET":
        form.full_name.data, form.phone.data, form.country.data = current_user.name, current_user.phone, "United States"
    elif form.validate_on_submit():
        _save_address(form)
        flash("Address saved.", "success")
        return redirect(url_for("account.addresses"))
    items = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.id).all()
    return render_template("account/addresses.html", addresses=items, form=form)


@bp.route("/addresses/<int:address_id>/edit", methods=["GET", "POST"])
def address_edit(address_id):
    address = _own_address(address_id)
    form = AddressForm(obj=address)
    if form.validate_on_submit():
        _save_address(form, address)
        flash("Address updated.", "success")
        return redirect(url_for("account.addresses"))
    return render_template("account/address_edit.html", form=form, address=address)


@bp.post("/addresses/<int:address_id>/delete")
def address_delete(address_id):
    address = _own_address(address_id)
    was_default = address.is_default
    db.session.delete(address)
    db.session.flush()
    if was_default:  # promote another address so a default always exists
        nxt = Address.query.filter_by(user_id=current_user.id).order_by(Address.id).first()
        if nxt is not None:
            nxt.is_default = True
    db.session.commit()
    flash("Address deleted.", "info")
    return redirect(url_for("account.addresses"))


@bp.post("/addresses/<int:address_id>/default")
def address_default(address_id):
    address = _own_address(address_id)
    Address.query.filter_by(user_id=current_user.id).update({"is_default": False})
    address.is_default = True
    db.session.commit()
    flash("Default address updated.", "success")
    return redirect(url_for("account.addresses"))


# ------------------------------------------------------------------ notifications
@bp.get("/notifications")
def notifications():
    page = _page()
    pagination = (Notification.query.filter_by(user_id=current_user.id)
                  .order_by(Notification.created_at.desc(), Notification.id.desc())
                  .paginate(page=page, per_page=20, error_out=False))
    if pagination.pages and page > pagination.pages:
        return redirect(url_for("account.notifications", page=pagination.pages))
    return render_template("account/notifications.html", notifications=pagination)


@bp.post("/notifications/read")
def notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("account.notifications"))
