from functools import wraps

from flask import flash, redirect, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first to access this page.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped
