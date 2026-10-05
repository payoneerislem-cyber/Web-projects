"""Admin area. The before_request guard protects EVERY route in this blueprint."""
from flask import Blueprint

from app.utils.decorators import enforce_admin

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def guard():
    return enforce_admin()


from app.routes.admin import dashboard  # noqa: E402,F401  (registers routes)
