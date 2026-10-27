"""Admin: store settings (shipping, tax, announcement)."""
from flask import current_app, flash, redirect, render_template, url_for

from app.forms.admin import SettingsForm
from app.routes.admin import bp
from app.services import settings_service


def _money(cents) -> str:
    return f"{cents / 100:.2f}"


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    cfg = current_app.config
    form = SettingsForm()
    if not form.is_submitted():
        form.announcement_text.data = settings_service.get("announcement_text", cfg["ANNOUNCEMENT_TEXT"], allow_empty=True)
        form.free_shipping_threshold.data = _money(settings_service.get_int("free_shipping_threshold", cfg["FREE_SHIPPING_THRESHOLD"]))
        form.standard_shipping_rate.data = _money(settings_service.get_int("standard_shipping_rate", cfg["SHIPPING_FLAT_RATE"]))
        form.express_shipping_rate.data = _money(settings_service.get_int("express_shipping_rate", cfg["EXPRESS_SHIPPING_RATE"]))
        try:
            form.tax_rate.data = format(float(settings_service.get("tax_rate", cfg["TAX_RATE"])) * 100, "g")
        except (TypeError, ValueError):
            form.tax_rate.data = "0"
        form.contact_email.data = settings_service.get("contact_email", cfg.get("CONTACT_EMAIL") or "")
    elif form.validate_on_submit():
        settings_service.save({
            "announcement_text": form.announcement_text.data or "",
            "free_shipping_threshold": form.cents["free_shipping_threshold"],
            "standard_shipping_rate": form.cents["standard_shipping_rate"],
            "express_shipping_rate": form.cents["express_shipping_rate"],
            "tax_rate": form.tax_fraction,
            "contact_email": form.contact_email.data or "",
        })
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", form=form)
