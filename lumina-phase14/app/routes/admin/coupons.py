"""Admin: coupons."""
from datetime import datetime, time

from flask import flash, redirect, render_template, url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.admin import CouponForm
from app.models import Coupon
from app.routes.admin import bp
from app.routes.admin._helpers import back, paginate, pagination_args
from app.services.coupon_service import normalize


def _cents_str(cents):
    return f"{cents / 100:.2f}" if cents else ""


@bp.get("/coupons")
def coupons():
    pagination = paginate(Coupon.query.order_by(Coupon.created_at.desc(), Coupon.id.desc()))
    return render_template("admin/coupons.html", coupons=pagination, args=pagination_args())


def _save(form: CouponForm, coupon: Coupon) -> bool:
    code = normalize(form.code.data)
    if Coupon.query.filter(Coupon.code == code, Coupon.id != (coupon.id or 0)).first():
        form.code.errors = [*form.code.errors, "This code already exists."]
        return False
    coupon.code, coupon.description = code, form.description.data or None
    coupon.discount_type, coupon.discount_value = form.discount_type.data, form.parsed["value"]
    coupon.minimum_order, coupon.maximum_discount = form.parsed["minimum"], form.parsed["maximum"]
    coupon.usage_limit, coupon.per_user_limit = form.usage_limit.data, form.per_user_limit.data
    coupon.start_date = datetime.combine(form.start_date.data, time.min) if form.start_date.data else None
    coupon.expiry_date = datetime.combine(form.expiry_date.data, time(23, 59, 59)) if form.expiry_date.data else None
    coupon.is_active = form.is_active.data
    db.session.add(coupon)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        form.code.errors = [*form.code.errors, "This code already exists."]
        return False
    return True


@bp.route("/coupons/new", methods=["GET", "POST"])
def coupon_new():
    form = CouponForm()
    if form.validate_on_submit() and _save(form, Coupon()):
        flash("Coupon created.", "success")
        return redirect(url_for("admin.coupons"))
    return render_template("admin/coupon_form.html", form=form, coupon=None)


@bp.route("/coupons/<int:coupon_id>/edit", methods=["GET", "POST"])
def coupon_edit(coupon_id):
    coupon = db.get_or_404(Coupon, coupon_id)
    form = CouponForm(obj=coupon)
    if not form.is_submitted():
        form.discount_value.data = _cents_str(coupon.discount_value) if coupon.discount_type == "fixed" else str(coupon.discount_value)
        form.minimum_order.data = _cents_str(coupon.minimum_order)
        form.maximum_discount.data = _cents_str(coupon.maximum_discount)
        form.start_date.data = coupon.start_date.date() if coupon.start_date else None
        form.expiry_date.data = coupon.expiry_date.date() if coupon.expiry_date else None
    if form.validate_on_submit() and _save(form, coupon):
        flash("Coupon saved.", "success")
        return redirect(url_for("admin.coupons"))
    return render_template("admin/coupon_form.html", form=form, coupon=coupon)


@bp.post("/coupons/<int:coupon_id>/toggle")
def coupon_toggle(coupon_id):
    coupon = db.get_or_404(Coupon, coupon_id)
    coupon.is_active = not coupon.is_active
    db.session.commit()
    flash(f"{coupon.code} is now {'active' if coupon.is_active else 'inactive'}.", "success")
    return back("admin.coupons")


@bp.post("/coupons/<int:coupon_id>/delete")
def coupon_delete(coupon_id):
    coupon = db.get_or_404(Coupon, coupon_id)
    if coupon.used_count or coupon.usages:
        flash(f"{coupon.code} has been used, so it can't be deleted. Deactivate it instead.", "error")
    else:
        db.session.delete(coupon)
        db.session.commit()
        flash("Coupon deleted.", "info")
    return redirect(url_for("admin.coupons"))
