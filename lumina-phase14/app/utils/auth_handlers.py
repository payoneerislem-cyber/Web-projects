"""Flask-Login configuration: what happens to anonymous visitors."""
from flask import flash, jsonify, redirect, request, url_for

from app.extensions import login_manager
from app.utils.errors import wants_json


def register_auth_handlers(app) -> None:
    login_manager.session_protection = "strong"

    @login_manager.unauthorized_handler
    def unauthorized():
        if wants_json():
            return jsonify({"ok": False, "error": "Authentication required."}), 401
        flash("Please log in to continue.", "info")
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
