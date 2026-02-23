from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, SelectField, FloatField, IntegerField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired, URL, ValidationError
from flask_ckeditor import CKEditorField
from tables.models import User
from wtforms.validators import DataRequired, Length, NumberRange, Email
from wtforms import HiddenField, FieldList, FormField

class RegisterForm(FlaskForm):
    username = StringField(
        "Nombre de usuario",
        validators=[
            DataRequired(),
            Length(min=4, max=50)
        ]
    )

    email = StringField(
        "Correo electrónico",
        validators=[
            DataRequired(),
            Email(message="Ingresá un email válido"),
            Length(max=150)
        ]
    )

    password = PasswordField(
        "Contraseña",
        validators=[
            DataRequired(),
            Length(min=6)
        ]
    )

    submit = SubmitField("Registrarme")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("El nombre de usuario ya existe")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("El correo electrónico ya está registrado")

class LoginForm(FlaskForm):
    username = StringField(
        "Nombre de usuario",
        validators=[DataRequired(), Length(min=4, max=50)]
    )

    password = PasswordField(
        "Contraseña",
        validators=[DataRequired()]
    )

    submit = SubmitField("Ingresar")

class NuevoClothesForm(FlaskForm):

    name = StringField(
        "Nombre de la prenda",
        validators=[
            DataRequired(),
            Length(min=3, max=100)
        ]
    )

    price = FloatField(
        "Precio",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    clothing_type = SelectField(
        "Tipo de prenda",
        coerce=int,
        validators=[DataRequired()]
    )

    image = FileField(
        "Imagen",
        validators=[
            DataRequired(),
            FileAllowed(
                ["jpg", "jpeg", "png"],
                "Solo imágenes JPG o PNG"
            )
        ]
    )

    color = StringField(
        "Color",
        validators=[DataRequired()],
        render_kw={
            "type": "color"
        }
    )

    submit = SubmitField("Crear prenda")


class AgregarCarritoForm(FlaskForm):

    color_id = SelectField(
        "Color",
        coerce=int,
        validators=[DataRequired()]
    )

    product_id = SelectField(
        "Talle",
        coerce=int,
        validators=[DataRequired()]
    )

    amount = IntegerField(
        "Cantidad",
        validators=[
            DataRequired(),
            NumberRange(min=1)
        ]
    )

    submit = SubmitField("Agregar al carrito")


# subform producto
class StockOrderItemForm(FlaskForm):
    product_id = HiddenField()
    amount = IntegerField(validators=[NumberRange(min=0)])


# form principal
class StockOrderForm(FlaskForm):
    items = FieldList(FormField(StockOrderItemForm))
    submit = SubmitField("Ingresar orden de productos")

class EditClothesForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired()])
    price = FloatField("Precio", validators=[DataRequired()])
    image = FileField("Imagen (opcional)")
    submit = SubmitField("Guardar cambios")