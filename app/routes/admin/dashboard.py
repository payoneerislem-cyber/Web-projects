from flask import render_template

from app.routes.admin import bp


@bp.get("")
def dashboard():
    return render_template("admin/dashboard.html")
