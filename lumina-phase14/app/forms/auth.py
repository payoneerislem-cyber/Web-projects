from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from app.utils.validators import validate_password_strength


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def password_policy(form, field):
    problems = validate_password_strength(field.data or "")
    if problems:
        raise ValidationError(" ".join(problems))


class LoginForm(FlaskForm):
    email = StringField("Email", filters=[_strip],
                        validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Remember me")


class RegisterForm(FlaskForm):
    name = StringField("Full name", filters=[_strip],
                       validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", filters=[_strip],
                        validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), password_policy])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", filters=[_strip],
                        validators=[DataRequired(), Email(), Length(max=255)])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), password_policy])
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
