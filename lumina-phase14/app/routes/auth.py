from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.forms.auth import ForgotPasswordForm, LoginForm, RegisterForm, ResetPasswordForm
from app.services import auth_service, cart_service
from app.services.auth_service import AuthError
from app.utils.redirects import safe_next_url

bp = Blueprint("auth", __name__)


def _after_login_url(user, next_url):
    if next_url:
        return next_url
    return url_for("admin.dashboard") if user.is_admin else url_for("main.index")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user = auth_service.register_user(form.name.data, form.email.data, form.password.data)
        except AuthError as exc:
            form.email.errors = [*form.email.errors, str(exc)]
        else:
            login_user(user)
            session.permanent = False
            cart_service.merge_guest_cart(user)
            flash(f"Welcome, {user.first_name}! Your account is ready.", "success")
            return redirect(url_for("main.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute;50 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    next_url = safe_next_url(request.args.get("next"))
    if form.validate_on_submit():
        try:
            user = auth_service.authenticate(form.email.data, form.password.data)
        except AuthError as exc:
            flash(str(exc), "error")
        else:
            if user is None:
                flash("Invalid email or password.", "error")
            else:
                login_user(user, remember=form.remember.data)
                session.permanent = bool(form.remember.data)
                user.touch_login()
                db.session.commit()
                cart_service.merge_guest_cart(user)
                flash(f"Welcome back, {user.first_name}!", "success")
                return redirect(_after_login_url(user, next_url))
    return render_template("auth/login.html", form=form, next_url=next_url)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        auth_service.request_password_reset(form.email.data)
        # Same response whether or not the account exists (no user enumeration).
        flash("If an account exists for that email, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def reset_password(token):
    user = auth_service.verify_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        auth_service.reset_password(user, form.password.data)
        flash("Your password has been updated. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)
