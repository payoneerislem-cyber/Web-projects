from flask_wtf import FlaskForm
from wtforms import RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ReviewForm(FlaskForm):
    rating = RadioField("Your rating", coerce=int, choices=[(5, "5"), (4, "4"), (3, "3"), (2, "2"), (1, "1")],
                        validators=[DataRequired(message="Please choose a rating from 1 to 5.")])
    title = StringField("Title (optional)", filters=[_strip], validators=[Optional(), Length(max=150)])
    content = TextAreaField("Your review (optional)", filters=[_strip], validators=[Optional(), Length(max=2000)])
