"""Error handlers: friendly pages for browsers, JSON for /api/ requests."""
import logging

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from app.extensions import db, login_manager

log = logging.getLogger(__name__)

MESSAGES = {
    400: "Your session expired or the request was invalid. Please refresh the page and try again.",
    401: "Please log in to continue.",
    405: "That action isn't allowed here.",
    403: "You don't have permission to access this page.",
    404: "The page you're looking for doesn't exist.",
    413: "The uploaded file is too large.",
    429: "Too many requests. Please slow down and try again shortly.",
    500: "Something went wrong on our side. Please try again later.",
}


def wants_json() -> bool:
    """True for /api/ paths, fetch() calls and JSON bodies."""
    return (
        request.path.startswith("/api/")
        or request.headers.get("X-Requested-With") == "fetch"
        or request.is_json
    )


def _respond(code: int, message: str | None = None):
    message = message or MESSAGES.get(code, "An error occurred.")
    if wants_json():
        return jsonify({"ok": False, "error": message}), code
    template = f"errors/{code}.html" if code in (403, 404, 500) else "errors/generic.html"
    return render_template(template, code=code, message=message), code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http(exc: HTTPException):
        code = exc.code or 500
        return _respond(code, MESSAGES.get(code))

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        # In debug mode let Flask's debugger show the traceback.
        if app.debug or app.testing:
            raise exc
        log.exception("Unhandled exception")
        db.session.rollback()
        return _respond(500)

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if wants_json():
            return jsonify({"ok": False, "error": "Authentication required."}), 401
        flash("Please log in to continue.", "info")
        next_url = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=next_url))
