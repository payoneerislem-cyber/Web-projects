from flask import current_app, render_template

from app.routes.admin import bp
from app.services import stats_service


@bp.get("")
def dashboard():
    return render_template("admin/dashboard.html", stats=stats_service.overview(),
                           currency_code=current_app.config["CURRENCY_CODE"])
