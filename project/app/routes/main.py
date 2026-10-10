"""Home and informational pages."""
from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user

from app.extensions import limiter
from app.forms.main import ContactForm, NewsletterForm
from app.services import catalog_service, contact_service, newsletter_service
from app.utils.redirects import safe_next_url

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("home.html", **catalog_service.home_sections())


@bp.get("/about")
def about():
    return render_template("pages/about.html")


@bp.get("/faq")
def faq():
    return render_template("pages/faq.html")


@bp.get("/terms")
def terms():
    return render_template("pages/terms.html")


@bp.get("/privacy")
def privacy():
    return render_template("pages/privacy.html")


@bp.route("/contact", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def contact():
    form = ContactForm()
    if request.method == "GET" and current_user.is_authenticated:
        form.name.data = current_user.name
        form.email.data = current_user.email
    if form.validate_on_submit():
        sent = contact_service.send_contact_message(
            form.name.data, form.email.data, form.subject.data, form.message.data)
        if sent:
            flash("Thanks! Your message has been sent. We'll reply soon.", "success")
            return redirect(url_for("main.contact"))
        flash("Sorry, we couldn't send your message right now. Please try again later.", "error")
    return render_template("pages/contact.html", form=form)


@bp.post("/newsletter")
@limiter.limit("5 per hour")
def newsletter():
    form = NewsletterForm()
    target = safe_next_url(request.form.get("next")) or url_for("main.index")
    if form.validate_on_submit():
        newsletter_service.subscribe(form.email.data)  # same reply whether new or existing
        flash("Thanks for subscribing! Watch your inbox for deals and new arrivals.", "success")
    else:
        flash("Please enter a valid email address.", "error")
    return redirect(target)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/styleguide")
def styleguide():
    """Living design-system reference. Only available in development/testing."""
    if not (current_app.debug or current_app.testing):
        abort(404)
    return render_template("styleguide.html")
