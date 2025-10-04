from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from models import User
from werkzeug.security import check_password_hash
from flask_login import current_user

class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Create Account")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("Email already registered.")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

    def validate(self, extra_validators=None):
        rv = super().validate(extra_validators=extra_validators)
        if not rv:
            return False
        user = User.query.filter_by(email=self.email.data.lower()).first()
        if not user or not check_password_hash(user.password_hash, self.password.data):
            self.email.errors.append("Invalid email or password.")
            return False
        self.user = user
        return True

class AlbumForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    description = TextAreaField("Description")
    visibility = SelectField("Visibility", choices=[("public", "Public"), ("private", "Private")], default="public")
    submit = SubmitField("Save")

class PhotoUploadForm(FlaskForm):
    album = SelectField("Album", coerce=int, validators=[DataRequired()])
    image = FileField("Image", validators=[DataRequired()])
    caption = StringField("Caption", validators=[Length(max=255)])
    tags = StringField("Tags (comma separated)")
    submit = SubmitField("Upload")

class VideoUploadForm(FlaskForm):
    album = SelectField("Album", coerce=int, validators=[DataRequired()])
    video = FileField("Video", validators=[DataRequired()])
    caption = StringField("Caption", validators=[Length(max=255)])
    tags = StringField("Tags (comma separated)")
    submit = SubmitField("Upload")

class EditProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("New Password", validators=[Length(min=6, max=128)])
    confirm = PasswordField("Confirm New Password", validators=[EqualTo("password")])
    submit = SubmitField("Update Profile")

    def validate_email(self, field):
        if field.data != current_user.email and User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("Email already registered.")