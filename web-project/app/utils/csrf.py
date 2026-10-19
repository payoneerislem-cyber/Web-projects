import secrets
from hmac import compare_digest

from flask import abort, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
TOKEN_KEY = "_csrf_token"


def generate_csrf_token():
    token = session.get(TOKEN_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[TOKEN_KEY] = token
    return token


def _validate_csrf():
    if request.method in SAFE_METHODS:
        return

    # API endpoints are all protected by @login_required. Let the
    # authentication guard handle anonymous API requests first; once a
    # session is authenticated, the CSRF token is mandatory.
    if request.endpoint and request.endpoint.startswith("api.") and "user_id" not in session:
        return

    expected = session.get(TOKEN_KEY)
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")

    if not expected or not supplied or not compare_digest(expected, supplied):
        abort(400, description="Invalid CSRF token")


def init_csrf(app):
    app.jinja_env.globals["csrf_token"] = generate_csrf_token
    app.before_request(_validate_csrf)
