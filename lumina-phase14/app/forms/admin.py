from decimal import Decimal, InvalidOperation

from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateField, FileField, IntegerField, MultipleFileField, SelectField,
                     StringField, TextAreaField)
from wtforms.validators import (DataRequired, Email, InputRequired, Length, NumberRange, Optional, Regexp)

from app.utils.money import to_cents

MAX_CENTS = 10**9


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _cents(field, *, required=False, minimum=0):
    """Parse a money field into cents; returns None if empty/invalid (errors are added)."""
    raw = (field.data or "").strip()
    if not raw:
        if required:
            field.errors = [*field.errors, "This field is required."]
        return None
    try:
        cents = to_cents(raw)
    except ValueError:
        field.errors = [*field.errors, "Enter a valid amount, e.g. 19.99."]
        return None
    if cents < minimum or cents > MAX_CENTS:
        field.errors = [*field.errors, "Enter an amount within the allowed range."]
        return None
    return cents


class ProductForm(FlaskForm):
    name = StringField("Name", filters=[_strip], validators=[DataRequired(), Length(max=200)])
    sku = StringField("SKU", filters=[_strip], validators=[
        DataRequired(), Length(max=64), Regexp(r"^[A-Za-z0-9._-]+$", message="Use letters, numbers, dots, dashes and underscores.")])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired(message="Choose a category.")])
    brand = StringField("Brand", filters=[_strip], validators=[Optional(), Length(max=80)])
    price = StringField("Price", filters=[_strip], validators=[DataRequired()])
    compare_at_price = StringField("Compare-at price (optional)", filters=[_strip], validators=[Optional()])
    cost_price = StringField("Cost price (optional)", filters=[_strip], validators=[Optional()])
    stock_quantity = IntegerField("Stock quantity", validators=[InputRequired(), NumberRange(min=0, max=1_000_000)])
    low_stock_threshold = IntegerField("Low-stock alert at", default=5, validators=[InputRequired(), NumberRange(min=0, max=100_000)])
    short_description = StringField("Short description", filters=[_strip], validators=[Optional(), Length(max=300)])
    description = TextAreaField("Description", filters=[_strip], validators=[Optional(), Length(max=10_000)])
    specs = TextAreaField("Specifications (one “Name: value” per line)", filters=[_strip], validators=[Optional(), Length(max=5000)])
    image_url = StringField("Add an image from a URL (https://…)", filters=[_strip], validators=[
        Optional(), Length(max=500), Regexp(r"^https://\S+$", message="Use a full https:// link.")])
    images = MultipleFileField("Upload images (JPG, PNG, WebP)")
    is_active = BooleanField("Visible in the store", default=True)
    is_featured = BooleanField("Featured")
    is_new = BooleanField("New arrival")
    is_best_seller = BooleanField("Best seller")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        self.cents = {
            "price": _cents(self.price, required=True),
            "compare_at_price": _cents(self.compare_at_price),
            "cost_price": _cents(self.cost_price),
        }
        if self.cents["compare_at_price"] is not None and self.cents["price"] is not None \
                and self.cents["compare_at_price"] <= self.cents["price"]:
            self.compare_at_price.errors = [*self.compare_at_price.errors, "Must be higher than the price."]
        self.specs_dict = {}
        for number, line in enumerate((self.specs.data or "").splitlines(), start=1):
            if not line.strip():
                continue
            key, sep, value = line.partition(":")
            if not sep or not key.strip() or not value.strip() or len(key.strip()) > 60 or len(value.strip()) > 200 \
                    or len(self.specs_dict) >= 30:
                self.specs.errors = [*self.specs.errors, f"Line {number} must look like “Name: value”."]
                break
            self.specs_dict[key.strip()] = value.strip()
        return ok and not any(f.errors for f in (self.price, self.compare_at_price, self.cost_price, self.specs))


class CategoryForm(FlaskForm):
    name = StringField("Name", filters=[_strip], validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", filters=[_strip], validators=[Optional(), Length(max=1000)])
    image_url = StringField("Image URL (optional)", filters=[_strip], validators=[
        Optional(), Length(max=500), Regexp(r"^(https://|/static/)\S+$", message="Use an https:// link.")])
    image = FileField("…or upload an image")
    is_active = BooleanField("Visible in the store", default=True)


class CouponForm(FlaskForm):
    code = StringField("Code", filters=[_strip], validators=[
        DataRequired(), Regexp(r"^[A-Za-z0-9_-]{3,50}$", message="3-50 letters, numbers, dashes or underscores.")])
    description = StringField("Description", filters=[_strip], validators=[Optional(), Length(max=200)])
    discount_type = SelectField("Type", choices=[("percentage", "Percentage (%)"), ("fixed", "Fixed amount")])
    discount_value = StringField("Value", filters=[_strip], validators=[DataRequired()])
    minimum_order = StringField("Minimum order (optional)", filters=[_strip], validators=[Optional()])
    maximum_discount = StringField("Maximum discount (optional)", filters=[_strip], validators=[Optional()])
    usage_limit = IntegerField("Total usage limit (optional)", validators=[Optional(), NumberRange(min=1, max=10_000_000)])
    per_user_limit = IntegerField("Uses per customer", default=1, validators=[InputRequired(), NumberRange(min=1, max=1000)])
    start_date = DateField("Starts on (optional)", validators=[Optional()])
    expiry_date = DateField("Expires on (optional)", validators=[Optional()])
    is_active = BooleanField("Active", default=True)

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        self.parsed = {"value": None, "minimum": 0, "maximum": None}
        if self.discount_type.data == "percentage":
            try:
                raw = Decimal((self.discount_value.data or "").strip())
                pct = int(raw)
                if not 1 <= pct <= 100 or raw != pct:
                    raise ValueError
                self.parsed["value"] = pct
            except (InvalidOperation, ValueError, OverflowError):
                self.discount_value.errors = [*self.discount_value.errors, "Enter a whole percentage from 1 to 100."]
        else:
            self.parsed["value"] = _cents(self.discount_value, required=True, minimum=1)
        self.parsed["minimum"] = _cents(self.minimum_order) or 0
        self.parsed["maximum"] = _cents(self.maximum_discount, minimum=1)
        if self.start_date.data and self.expiry_date.data and self.expiry_date.data < self.start_date.data:
            self.expiry_date.errors = [*self.expiry_date.errors, "Must be on or after the start date."]
        return ok and not any(f.errors for f in (self.discount_value, self.minimum_order, self.maximum_discount, self.expiry_date))


class SettingsForm(FlaskForm):
    announcement_text = StringField("Announcement bar text (leave empty to hide)", filters=[_strip], validators=[Optional(), Length(max=200)])
    free_shipping_threshold = StringField("Free shipping from", filters=[_strip], validators=[DataRequired()])
    standard_shipping_rate = StringField("Standard shipping price", filters=[_strip], validators=[DataRequired()])
    express_shipping_rate = StringField("Express shipping price", filters=[_strip], validators=[DataRequired()])
    tax_rate = StringField("Sales tax rate (%)", filters=[_strip], validators=[Optional()])
    contact_email = StringField("Contact email", filters=[_strip], validators=[Optional(), Email(), Length(max=255)])

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        self.cents = {name: _cents(getattr(self, name), required=True)
                      for name in ("free_shipping_threshold", "standard_shipping_rate", "express_shipping_rate")}
        self.tax_fraction = "0"
        raw = (self.tax_rate.data or "").strip()
        if raw:
            try:
                pct = Decimal(raw)
                if not pct.is_finite() or not 0 <= pct <= 50:
                    raise InvalidOperation
                self.tax_fraction = format(pct / 100, "f")
            except InvalidOperation:
                self.tax_rate.errors = [*self.tax_rate.errors, "Enter a percentage between 0 and 50."]
        return ok and not any(getattr(self, n).errors for n in ("free_shipping_threshold", "standard_shipping_rate",
                                                               "express_shipping_rate", "tax_rate"))
