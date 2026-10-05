"""Authorization helpers. Enforced on the backend, never just hidden in the UI."""
from functools import wraps

from flask import abort, current_app
from flask_login import current_user


def enforce_admin():
    """Return a response if the visitor isn't an admin, else None."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()  # -> login page / 401 JSON
    if not current_user.is_admin:
        abort(403)
    return None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        denied = enforce_admin()
        if denied is not None:
            return denied
        return view(*args, **kwargs)

    return wrapped
