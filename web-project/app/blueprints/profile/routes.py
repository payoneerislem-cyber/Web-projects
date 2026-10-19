from flask import Blueprint, flash, redirect, session, url_for, request

from app.services.profile import save_profile_picture
from app.utils.decorators import login_required

bp = Blueprint("profile", __name__)


@bp.post("/upload_profile")
@login_required
def upload_profile():
    success, message = save_profile_picture(session["user_id"], request.files.get("avatar"))
    flash(message, "success" if success else "error")
    return redirect(url_for("main.budget"))
