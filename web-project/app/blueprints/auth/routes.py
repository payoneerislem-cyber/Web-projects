from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.services.auth import (
    authenticate,
    change_password,
    generate_otp,
    is_otp_valid,
    normalize_email,
    otp_expiration,
    register_user,
)
from app.services.email import send_otp_email
from app.repositories import UserRepository
from app.utils.decorators import login_required

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("main.budget"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        email = request.form.get("email", "")
        _, error = register_user(username, password, email)
        if error:
            flash(error, "error")
            return redirect(url_for("auth.register"))
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("main.budget"))

    if request.method == "POST":
        user = authenticate(request.form.get("username"), request.form.get("password"))
        if not user:
            flash("Username or password is incorrect.", "error")
            return redirect(url_for("auth.login"))

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session.permanent = bool(request.form.get("remember"))
        return redirect(url_for("main.budget"))

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password_route():
    if request.method == "POST":
        success, message = change_password(
            session["user_id"],
            request.form.get("old_password"),
            request.form.get("new_password"),
        )
        flash(message, "success" if success else "error")
        if success:
            session.clear()
            return redirect(url_for("auth.login"))
        return redirect(url_for("main.budget"))

    return render_template("auth/change_password.html")


@bp.route("/reset_request", methods=["GET", "POST"])
def reset_request():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        user = UserRepository.get_by_email(email)
        if not user:
            flash("No account was found with this email address.", "error")
            return redirect(url_for("auth.reset_request"))

        otp = generate_otp()
        if not send_otp_email(email, otp):
            flash("Unable to send the verification email. Please check mail settings.", "error")
            return redirect(url_for("auth.reset_request"))

        session["user_reset_id"] = user["id"]
        session["user_otp_code"] = otp
        session["user_otp_expires_at"] = otp_expiration(current_app.config["OTP_TTL_SECONDS"])
        session.pop("otp_verified", None)
        flash("Verification code sent successfully.", "success")
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/reset_request.html")


@bp.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if session.get("user_reset_id") is None:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        confirmed_otp = request.form.get("otp_code", "").strip()
        if is_otp_valid(
            session.get("user_otp_code"),
            confirmed_otp,
            session.get("user_otp_expires_at"),
        ):
            session["otp_verified"] = True
            flash("The code is correct.", "success")
            return redirect(url_for("auth.reset_password"))

        flash("The code is incorrect or expired.", "error")
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/verify_otp.html")


@bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if not session.get("otp_verified"):
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        if len(new_password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("auth.reset_password"))

        user_id = session["user_reset_id"]
        from werkzeug.security import generate_password_hash

        UserRepository.update_password(user_id, generate_password_hash(new_password))
        session.clear()
        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")
