from typing import Optional
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, HiddenField
from wtforms.fields.core import IntegerField, RadioField
from wtforms.validators import DataRequired, Email, Length, ValidationError, Optional


class MessageForm(FlaskForm):
    """Form for adding/editing messages."""

    text = TextAreaField('text', validators=[DataRequired(), Length(max=140)])


class ReplyForm(FlaskForm):
    """Form for replying to an existing message."""

    text = TextAreaField('Reply', validators=[DataRequired(), Length(max=140)])


class QuotePostForm(FlaskForm):
    """Form for quote-posting an existing message."""

    text = TextAreaField('Quote', validators=[DataRequired(), Length(max=140)])


class AIAssistantForm(FlaskForm):
    """Form for local AI assistant tasks."""

    task = RadioField(
        'Task',
        validators=[DataRequired()],
        choices=[
            ('compose', 'Compose help'),
            ('summary', 'Thread summary'),
            ('rewrite', 'Tone rewrite'),
        ],
        default='compose',
    )
    source_message_id = HiddenField()
    input_text = TextAreaField('Input text', validators=[DataRequired(), Length(max=2000)])
    tone = StringField('(Optional) Rewrite tone (e.g. professional, witty, friendly)')


class UserAddForm(FlaskForm):
    """Form for adding users."""

    username = StringField('Username', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Length(min=6)])
    image_url = StringField('(Optional) Image URL')


class LoginForm(FlaskForm):
    """Login form."""

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[Length(min=6)])

class UserEditForm(FlaskForm):
    """Form for edit user's bio."""

    username = StringField('Username', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    image_url = StringField('(Optional) Image URL')
    header_image_url = StringField('(Optional) Header Image URL')
    bio = StringField('(Optional) Bio')
    password = PasswordField('Password', validators=[Length(min=6)])