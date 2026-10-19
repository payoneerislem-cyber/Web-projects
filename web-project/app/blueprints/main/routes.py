from flask import Blueprint, redirect, render_template, session, url_for

from app.services.budget import get_user_budget_data
from app.utils.decorators import login_required

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    if "user_id" in session:
        return redirect(url_for("main.budget"))
    return redirect(url_for("auth.login"))


@bp.get("/budget")
@login_required
def budget():
    data = get_user_budget_data(session["user_id"])
    return render_template("dashboard/index.html", **data)


@bp.get("/health")
def health():
    return {"status": "ok", "service": "budget-tracker"}, 200
