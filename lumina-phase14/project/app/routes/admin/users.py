"""Admin: customers and staff accounts."""
from flask import flash, render_template, request
from flask_login import current_user
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Order, Role, User
from app.routes.admin import bp
from app.routes.admin._helpers import back, like, paginate, pagination_args


@bp.get("/users")
def users():
    q = " ".join((request.args.get("q") or "").split())[:100]
    role = request.args.get("role", "")
    query = User.query
    if role in Role.ALL:
        query = query.filter(User.role == role)
    if q:
        pattern = like(q)
        query = query.filter(or_(User.email.ilike(pattern, escape="\\"), User.name.ilike(pattern, escape="\\")))
    pagination = paginate(query.order_by(User.created_at.desc(), User.id.desc()))
    counts = dict(db.session.query(Order.user_id, func.count(Order.id))
                  .filter(Order.user_id.in_([u.id for u in pagination.items] or [0])).group_by(Order.user_id).all())
    return render_template("admin/users.html", users=pagination, q=q, role=role, order_counts=counts,
                           roles=Role.ALL, args=pagination_args())


def _target(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You can't change your own account from here.", "error")
        return None
    return user


@bp.post("/users/<int:user_id>/toggle-active")
def user_toggle_active(user_id):
    user = _target(user_id)
    if user is not None:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"{user.email} was {'re-enabled' if user.is_active else 'disabled'}.", "success")
    return back("admin.users")


@bp.post("/users/<int:user_id>/role")
def user_role(user_id):
    user = _target(user_id)
    new_role = request.form.get("role", "")
    if user is not None:
        if new_role not in Role.ALL:
            flash("Unknown role.", "error")
        else:
            user.role = new_role
            db.session.commit()
            flash(f"{user.email} is now {new_role}.", "success")
    return back("admin.users")
