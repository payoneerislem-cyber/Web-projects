from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, Regexp

from app.forms.auth import password_policy

PHONE = Regexp(r"^[0-9+()\-\s.]{6,30}$", message="Enter a valid phone number.")


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ProfileForm(FlaskForm):
    name = StringField("Full name", filters=[_strip], validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField("Phone (optional)", filters=[_strip], validators=[Optional(), PHONE])


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired(), Length(max=128)])
    new_password = PasswordField("New password", validators=[DataRequired(), password_policy])
    confirm_password = PasswordField("Confirm new password", validators=[
        DataRequired(), EqualTo("new_password", message="Passwords must match.")])


class AddressForm(FlaskForm):
    label = StringField("Label (e.g. Home, Work)", filters=[_strip], validators=[Optional(), Length(max=50)])
    full_name = StringField("Full name", filters=[_strip], validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField("Phone", filters=[_strip], validators=[DataRequired(), PHONE])
    line1 = StringField("Address line 1", filters=[_strip], validators=[DataRequired(), Length(max=200)])
    line2 = StringField("Address line 2 (optional)", filters=[_strip], validators=[Optional(), Length(max=200)])
    city = StringField("City", filters=[_strip], validators=[DataRequired(), Length(max=100)])
    state = StringField("State / region (optional)", filters=[_strip], validators=[Optional(), Length(max=100)])
    postal_code = StringField("Postal code", filters=[_strip], validators=[DataRequired(), Length(max=20)])
    country = StringField("Country", filters=[_strip], validators=[DataRequired(), Length(max=100)])
    is_default = BooleanField("Use as my default address")
