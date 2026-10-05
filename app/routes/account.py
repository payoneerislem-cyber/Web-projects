"""Customer account area. Every route requires login (enforced in before_request)."""
from flask import Blueprint, current_app, render_template
from flask_login import current_user

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    return None


@bp.get("")
def dashboard():
    return render_template("account/dashboard.html")
