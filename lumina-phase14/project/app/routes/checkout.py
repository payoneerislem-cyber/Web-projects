"""Checkout and order confirmation."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.forms.checkout import CheckoutForm
from app.models import Address
from app.services import cart_service, order_service, payment, pricing_service
from app.services.order_service import CheckoutError
from app.utils.validators import normalize_email

bp = Blueprint("checkout", __name__)


def _saved_addresses():
    addresses = list(current_user.addresses)
    addresses.sort(key=lambda a: (not a.is_default, a.id))
    return addresses


def _address_from_form(form, addresses):
    """The address snapshot for the order, or None if the choice isn't valid."""
    if form.address_id.data == "new":
        return {
            "full_name": form.full_name.data, "phone": form.phone.data,
            "line1": form.line1.data, "line2": form.line2.data or "",
            "city": form.city.data, "state": form.state.data or "",
            "postal_code": form.postal_code.data, "country": form.country.data,
        }
    chosen = next((a for a in addresses if str(a.id) == form.address_id.data), None)
    return chosen.to_snapshot() if chosen else None


def _render(form, cart, addresses, providers):
    data = cart_service.serialize(cart)
    method = form.shipping_method.data if form.shipping_method.data in pricing_service.SHIPPING_METHODS \
        else pricing_service.DEFAULT_SHIPPING_METHOD
    options = pricing_service.shipping_options(data["subtotal"], data["discount"])
    selected = next(o for o in options if o["key"] == method)
    return render_template("checkout/checkout.html", form=form, cart=data, addresses=addresses,
                           providers=providers, shipping_options=options, selected_shipping=selected)


@bp.route("/checkout", methods=["GET", "POST"])
@limiter.limit("20 per minute", methods=["POST"])
@login_required
def index():
    if request.method == "GET":
        cart, notices = cart_service.reconcile(cart_service.get_cart())  # tidy up stale lines
        for notice in notices:
            flash(notice, "warning")
    else:
        # Never silently change what the customer is buying: on submit the order service
        # validates strictly and sends them back to the cart if anything changed.
        cart = cart_service.get_cart()
    if cart is None or not cart.items:
        flash("Your cart is empty.", "info")
        return redirect(url_for("cart.view"))

    addresses = _saved_addresses()
    providers = payment.available_providers()
    form = CheckoutForm()
    form.address_id.choices = [(str(a.id), a.line1) for a in addresses] + [("new", "Use a new address")]
    form.shipping_method.choices = [(k, v["label"]) for k, v in pricing_service.SHIPPING_METHODS.items()]
    form.payment_method.choices = [(p.key, p.label) for p in providers]

    if request.method == "GET":
        form.full_name.data = current_user.name
        form.email.data = current_user.email
        form.phone.data = current_user.phone or (addresses[0].phone if addresses else "")
        form.address_id.data = str(addresses[0].id) if addresses else "new"
        form.shipping_method.data = pricing_service.DEFAULT_SHIPPING_METHOD
        form.payment_method.data = providers[0].key
        form.country.data = "United States"
    elif form.validate_on_submit():
        address = _address_from_form(form, addresses)
        if address is None:
            flash("Please choose a valid shipping address.", "error")
        else:
            try:
                order = order_service.create_order(
                    current_user, cart,
                    customer={"full_name": form.full_name.data, "email": normalize_email(form.email.data),
                              "phone": form.phone.data},
                    address=address, shipping_method=form.shipping_method.data,
                    payment_method=form.payment_method.data,
                    payment_payload={"scenario": form.demo_scenario.data},
                    notes=form.notes.data or "",
                    save_address=bool(form.save_address.data and form.address_id.data == "new"),
                )
            except CheckoutError as exc:
                flash(str(exc), "error")
                if exc.needs_cart_fix:
                    return redirect(url_for("cart.view"))
                cart = cart_service.get_cart()  # the failed attempt rolled back: reload fresh
                if cart is None or not cart.items:
                    return redirect(url_for("cart.view"))
            else:
                return redirect(url_for("checkout.confirmation", order_number=order.order_number))
    return _render(form, cart, addresses, providers)


@bp.get("/checkout/confirmation/<order_number>")
@login_required
def confirmation(order_number):
    order = order_service.get_order_for_user(current_user, order_number)
    try:
        payment_label = payment.get_provider(order.payment_method).label
    except KeyError:
        payment_label = order.payment_method
    method = pricing_service.SHIPPING_METHODS.get(order.shipping_method, {})
    return render_template("checkout/confirmation.html", order=order, payment_label=payment_label,
                           shipping_label=method.get("label", order.shipping_method), shipping_eta=method.get("eta", ""))
