from flask_wtf import FlaskForm
from wtforms import BooleanField, RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp


def _strip(value):
    return value.strip() if isinstance(value, str) else value


REQUIRED_FOR_NEW_ADDRESS = ("line1", "city", "postal_code", "country")


class CheckoutForm(FlaskForm):
    # 1. contact
    full_name = StringField("Full name", filters=[_strip], validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", filters=[_strip], validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone", filters=[_strip], validators=[
        DataRequired(), Regexp(r"^[0-9+()\-\s.]{6,30}$", message="Enter a valid phone number.")])

    # 2. address: a saved address id, or "new" plus the fields below
    address_id = RadioField("Shipping address", validators=[DataRequired(message="Please choose a shipping address.")])
    line1 = StringField("Address line 1", filters=[_strip], validators=[Optional(), Length(max=200)])
    line2 = StringField("Address line 2 (optional)", filters=[_strip], validators=[Optional(), Length(max=200)])
    city = StringField("City", filters=[_strip], validators=[Optional(), Length(max=100)])
    state = StringField("State / region (optional)", filters=[_strip], validators=[Optional(), Length(max=100)])
    postal_code = StringField("Postal code", filters=[_strip], validators=[Optional(), Length(max=20)])
    country = StringField("Country", filters=[_strip], validators=[Optional(), Length(max=100)])
    save_address = BooleanField("Save this address for next time")

    # 3-4. shipping + payment
    shipping_method = RadioField("Shipping method", validators=[DataRequired(message="Please choose a shipping method.")])
    payment_method = RadioField("Payment method", validators=[DataRequired(message="Please choose a payment method.")])
    demo_scenario = RadioField("Test outcome", choices=[("approve", "Approve the payment"), ("decline", "Decline the payment")],
                               default="approve", validate_choice=False)

    # 5. review
    notes = TextAreaField("Order notes (optional)", filters=[_strip], validators=[Optional(), Length(max=500)])
    accept_terms = BooleanField("I agree to the Terms & Conditions and Privacy Policy",
                                validators=[DataRequired(message="You must accept the terms to place an order.")])

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if self.address_id.data == "new":
            for name in REQUIRED_FOR_NEW_ADDRESS:
                field = getattr(self, name)
                if not (field.data or "").strip():
                    field.errors = [*field.errors, "This field is required."]
                    ok = False
        return ok
