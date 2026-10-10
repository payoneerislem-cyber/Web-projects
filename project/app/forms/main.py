from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ContactForm(FlaskForm):
    name = StringField("Your name", filters=[_strip], validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", filters=[_strip], validators=[DataRequired(), Email(), Length(max=255)])
    subject = StringField("Subject", filters=[_strip], validators=[DataRequired(), Length(min=3, max=150)])
    message = TextAreaField("Message", filters=[_strip], validators=[DataRequired(), Length(min=10, max=2000)])


class NewsletterForm(FlaskForm):
    email = StringField("Email", filters=[_strip], validators=[DataRequired(), Email(), Length(max=255)])
