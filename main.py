from flask import Flask, abort, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_bootstrap import Bootstrap
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RegisterForm, LoginForm, NuevoClothesForm, AgregarCarritoForm, EditClothesForm
from extensions import db
from dotenv import load_dotenv
import os
from auxiliary_functions import Save_and_resize_image
from sqlalchemy.orm import joinedload
from sqlalchemy import select, func, extract
from datetime import datetime, timedelta
import mercadopago
from analytics.restock_engine import generate_restock_recommendations


load_dotenv()

sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))
PUBLIC_URL = os.getenv("PUBLIC_URL")


app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

IMAGE_SIZE = (800, 800)  # tamaño estándar

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
Bootstrap(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


# Expira ordenes que se quedaron mas de 15 min sin pagar (se pueden llegar a pagar igual despues)
def expire_pending_orders():

    now = datetime.utcnow()

    expired_orders = (
        User_order.query
        .options(
            joinedload(User_order.order_products)
            .joinedload(Order_product.product)
        )
        .filter(
            User_order.status == "pending",
            User_order.expires_at <= now
        )
        .all()
    )

    for order in expired_orders:

        for op in order.order_products:
            op.product.stock += op.amount

        order.status = "expired"

    if expired_orders:
        db.session.commit()


# Carga el usuario
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Si no hay un usuario logueado
@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for("login"))


# CREATE DATABASE
database_url = os.getenv("DATABASE_URL")

if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///athletix.db'

if database_url:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
    }


db.init_app(app)


with app.app_context():
    from tables.models import Brand,Cart_item,Clothes,Color,Order_product,Product,Size,Stock_order_product,Stock_order,User_order,User, Clothing_type
    db.create_all()



@app.before_request
def handle_expirations():
    expire_pending_orders()


# Solo permite usuarios admin
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.is_admin is False:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


# Home page de la tienda
@app.route('/')
def home_page():

    selected_type = request.args.get("type", type=int)

    query = (
        Clothes.query
        .options(
            joinedload(Clothes.brand),
            joinedload(Clothes.clothing_type),
            joinedload(Clothes.products)
        )
        .filter(Clothes.discontinued == False)
    )

    if selected_type:
        query = query.filter(Clothes.clothing_type_id == selected_type)

    clothes_list = query.all()

    clothing_types = Clothing_type.query.all()

    return render_template(
        "index.html",
        clothes_list=clothes_list,
        clothing_types=clothing_types,
        selected_type=selected_type
    )


# Agregar un producto al carrito del usuario (NO PARA ADMINS)
@app.route("/carrito/agregar/<int:clothes_id>", methods=["GET", "POST"])
@login_required
def agregar_carrito(clothes_id):

    if current_user.is_admin:
        return redirect(url_for("home_page"))

    clothes = db.get_or_404(Clothes, clothes_id)

    products = (
        Product.query
        .options(
            joinedload(Product.size),
            joinedload(Product.color)
        )
        .filter(
            Product.clothes_id == clothes.id,
            Product.stock > 0
        )
        .all()
    )

    color_map = {}

    for p in products:   # 🔥 CORREGIDO

        cid = str(p.color.id)

        if cid not in color_map:
            color_map[cid] = {
                "red": p.color.red,
                "green": p.color.green,
                "blue": p.color.blue,
                "products": []
            }

        color_map[cid]["products"].append({
            "product_id": p.id,
            "size": p.size.name,
            "stock": p.stock
        })

    form = AgregarCarritoForm()

    form.color_id.choices = [
        (cid, f"RGB({data['red']},{data['green']},{data['blue']})")
        for cid, data in color_map.items()
    ]

    # 👇 importante
    if request.method == "POST":

        selected_color = request.form.get("color_id")

        if selected_color and selected_color in color_map:
            form.product_id.choices = [
                (p["product_id"], p["size"])
                for p in color_map[selected_color]["products"]
            ]

    if form.validate_on_submit():

        try:

            product = db.get_or_404(Product, form.product_id.data)

            if product.clothes_id != clothes.id:
                flash("Producto inválido", "danger")
                return redirect(request.url)

            if product.stock <= 0:
                flash("Producto sin stock", "danger")
                return redirect(request.url)

            if form.amount.data <= 0:
                flash("Cantidad inválida", "danger")
                return redirect(request.url)

            if form.amount.data > product.stock:
                flash("No hay suficiente stock disponible", "danger")
                return redirect(request.url)

            # 🔎 buscar si ya existe en el carrito
            existing_item = Cart_item.query.filter_by(
                user_id=current_user.id,
                product_id=product.id
            ).first()

            # cantidad nueva que quiere agregar
            new_amount = form.amount.data

            # cantidad actual en carrito
            current_cart_amount = existing_item.amount if existing_item else 0

            # cantidad total futura
            total_amount = current_cart_amount + new_amount

            # 🚨 validar stock acumulado
            if total_amount > product.stock:
                flash(
                    f"Stock insuficiente. Ya tenés {current_cart_amount} en el carrito y el stock es {product.stock}.",
                    "danger"
                )
                return redirect(request.url)

            # 🧠 carrito inteligente acumulativo
            if existing_item:
                existing_item.amount = total_amount
            else:
                cart_item = Cart_item(
                    product=product,
                    user=current_user,
                    amount=new_amount
                )
                db.session.add(cart_item)

            db.session.commit()

            flash("Producto agregado al carrito", "success")
            return redirect(url_for("home_page"))

        except Exception:
            db.session.rollback()
            flash("Ocurrió un error inesperado", "danger")
            return redirect(request.url)

    return render_template(
        "agregar_carrito.html",
        clothes=clothes,
        form=form,
        color_map=color_map
    )


# Registrar un usuario nuevo (nombre de usuario es único)
@app.route('/register', methods=['GET', 'POST'])
def register():

    # 🔐 Si ya está logueado, afuera
    if current_user.is_authenticated:
        return redirect(url_for('home_page'))

    form = RegisterForm()

    if form.validate_on_submit():
        new_user = User(
            username=form.username.data,
            password=generate_password_hash(
                form.password.data,
                method='pbkdf2:sha256',
                salt_length=8
            ),
            is_admin=False
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('home_page'))

    return render_template("register.html", form=form)


# Ingresar a un usuario
@app.route('/login', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:
        return redirect(url_for('home_page'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if not user or not check_password_hash(user.password, form.password.data):
            # ⛔ Error mostrado
            form.password.errors.append("Usuario o contraseña incorrectos")
        else:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home_page'))

    return render_template("login.html", form=form)


# Cierra sesión
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home_page'))


# Muestra productos en el carrito actual y ordenes previas del usuario con numero de orden (NO ADMIN)
@app.route('/cart', methods=["GET", "POST"])
@login_required
def cart_page():

    if current_user.is_admin:
        return redirect(url_for("home_page"))

    remove_id = request.form.get("remove_item")

    if remove_id:

        item = db.get_or_404(Cart_item, int(remove_id))

        if item.user_id == current_user.id:
            db.session.delete(item)
            db.session.commit()
            flash("Producto eliminado del carrito", "warning")

        return redirect(url_for("cart_page"))

    cart_items = (
        Cart_item.query
        .options(
            joinedload(Cart_item.product)
                .joinedload(Product.clothes),

            joinedload(Cart_item.product)
                .joinedload(Product.clothes)
                    .joinedload(Clothes.brand),

            joinedload(Cart_item.product)
                .joinedload(Product.size),

            joinedload(Cart_item.product)
                .joinedload(Product.color)
        )
        .filter_by(user_id=current_user.id)
        .all()
    )

    cart_total = 0
    cart_has_stock_error = False

    for item in cart_items:

        item.stock_error = False

        if item.amount > item.product.stock:
            item.stock_error = True
            cart_has_stock_error = True

        # ✅ precio desde clothes
        cart_total += item.amount * item.product.clothes.price

    user_orders = (
        User_order.query
        .options(
            joinedload(User_order.order_products)
            .joinedload(Order_product.product)
            .joinedload(Product.color)
        )
        .filter_by(user_id=current_user.id)
        .order_by(User_order.id.desc())
        .all()
    )

    return render_template(
        "my_cart.html",
        cart_items=cart_items,
        cart_total=cart_total,
        cart_has_stock_error=cart_has_stock_error,
        user_orders=user_orders
    )


# Pagina de checkout antes de pagar (NO ADMIN)
@app.route("/checkout")
@login_required
def checkout_page():

    if current_user.is_admin:
        return redirect(url_for("home_page"))

    cart_items = (
        Cart_item.query
        .options(
            joinedload(Cart_item.product)
            .joinedload(Product.clothes),
            joinedload(Cart_item.product)
            .joinedload(Product.size),
            joinedload(Cart_item.product)
            .joinedload(Product.color)
        )
        .filter_by(user_id=current_user.id)
        .all()
    )

    cart_total = 0
    for item in cart_items:
        cart_total += item.amount*item.product.clothes.price

    if not cart_items:
        flash("Carrito vacío", "warning")
        return redirect(url_for("cart_page"))

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        cart_total=cart_total
    )


# Logistica del pago (NO ADMIN)
@app.route("/checkout/pay", methods=["POST"])
@login_required
def checkout_pay():

    if current_user.is_admin:
        return redirect(url_for("home_page"))

    try:

        cart_items = (
            Cart_item.query
            .options(
                joinedload(Cart_item.product)
                .joinedload(Product.clothes),
                joinedload(Cart_item.product)
                .joinedload(Product.size)
            )
            .filter_by(user_id=current_user.id)
            .all()
        )

        if not cart_items:
            flash("Carrito vacío", "warning")
            return redirect(url_for("cart_page"))

        product_ids = [item.product_id for item in cart_items]

        locked_products = (
            db.session.execute(
                select(Product)
                .where(Product.id.in_(product_ids))
                .with_for_update()
            )
            .scalars()
            .all()
        )

        product_map = {p.id: p for p in locked_products}

        for item in cart_items:
            if item.amount > product_map[item.product_id].stock:
                flash("Stock insuficiente", "danger")
                db.session.rollback()
                return redirect(url_for("cart_page"))

        order = User_order(
            user=current_user,
            total=0,
            status="pending",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=15)

        )

        db.session.add(order)
        db.session.flush()

        total = 0
        mp_items = []

        for item in cart_items:

            product = product_map[item.product_id]
            clothes = product.clothes
            price = float(clothes.price)

            op = Order_product(
                user_order=order,
                product=product,
                amount=item.amount,
                price=price,
                clothes_name=clothes.name,
                size_name=product.size.name
            )

            db.session.add(op)

            product.stock -= item.amount

            subtotal = price * item.amount
            total += subtotal

            mp_items.append({
                "title": clothes.name,
                "quantity": item.amount,
                "unit_price": price,
                "currency_id": "ARS"
            })

        order.total = total


        preference_data = {
            "items": mp_items,
            "external_reference": str(order.id),
            "notification_url": f"{PUBLIC_URL}/mp/webhook",
            "back_urls": {
                "success": f"{PUBLIC_URL}/payment_success",
                "failure": f"{PUBLIC_URL}/payment_failure",
                "pending": f"{PUBLIC_URL}/payment_pending"
            },
            "auto_return": "approved",

        }

        pref = sdk.preference().create(preference_data)

        print("MP PREF RESPONSE:", pref)

        if pref["status"] != 201:
            raise Exception(pref)

        order.mp_preference_id = pref["response"]["id"]

        for item in cart_items:
            db.session.delete(item)

        db.session.commit()

        return redirect(pref["response"]["init_point"])

    except Exception as e:
        db.session.rollback()
        print("CHECKOUT ERROR:", e)
        flash("Error iniciando pago", "danger")
        return redirect(url_for("cart_page"))


# webhook de mercadopago
@app.route("/mp/webhook", methods=["POST"])
def mp_webhook():

    data = request.json
    print("WEBHOOK:", data)

    topic = data.get("topic")

    if topic == "merchant_order":

        merchant_url = data.get("resource")

        mo = sdk.merchant_order().get(merchant_url.split("/")[-1])
        payments = mo["response"]["payments"]

        for p in payments:

            payment = sdk.payment().get(p["id"])

            if payment["response"]["status"] == "approved":

                order_id = int(
                    payment["response"]["external_reference"]
                )

                order = User_order.query.get(order_id)

                if not order:
                    return "OK", 200

                if order.status == "expired":
                    # llegó pago tarde
                    order.status = "paid"
                    order.order_number = str(p["id"])
                    db.session.commit()
                    return "OK", 200

    return "OK", 200


# Marca que el pago fue exitoso y redirecciona
@app.route("/payment_success")
def payment_success():
    flash("Pago realizado correctamente", "success")
    return redirect(url_for("cart_page"))


# Marca que el pago fue rechazado y redirecciona
@app.route("/payment_failure")
def payment_failure():
    flash("El pago fue rechazado", "danger")
    return redirect(url_for("cart_page"))


# Marca que el pago quedo pendiente y redirecciona
@app.route("/payment_pending")
def payment_pending():
    flash("El pago quedó pendiente", "warning")
    return redirect(url_for("cart_page"))


# Permite editar atributos de una prenda (nombre, imagen, precio) (SOLO ADMIN)
@app.route('/stock/editar/<int:clothes_id>', methods=["GET", "POST"])
@admin_only
def edit_clothes_page(clothes_id):

    clothes = db.get_or_404(Clothes, clothes_id)
    form = EditClothesForm(obj=clothes)

    if form.validate_on_submit():

        try:
            clothes.name = form.name.data
            clothes.price = form.price.data

            # carpeta uploads
            upload_folder = os.path.join(
                current_app.root_path,
                "static",
                "uploads"
            )

            # si sube imagen nueva
            if form.image.data:

                file = form.image.data

                # validación simple
                if not file.mimetype.startswith("image/"):
                    flash("El archivo debe ser una imagen válida", "danger")
                    return redirect(request.url)

                # borrar imagen vieja
                if clothes.image_filename:
                    old_path = os.path.join(upload_folder, clothes.image_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)

                filename = Save_and_resize_image(
                    file=file,
                    upload_folder=upload_folder,
                    size=(800, 800)
                )

                clothes.image_filename = filename
                clothes.image_path = os.path.join(
                    upload_folder,
                    filename
                )

            db.session.commit()
            flash("Prenda actualizada correctamente", "success")

            return redirect(url_for("stock_page"))

        except Exception:
            db.session.rollback()
            flash("Error al actualizar la prenda", "danger")

    return render_template(
        "edit_clothes.html",
        clothes=clothes,
        form=form
    )


# Saca 1 stock de un producto (SOLO ADMIN)
@app.route("/stock/remove", methods=["POST"])
@admin_only
def remove_stock():

    product = db.get_or_404(
        Product,
        int(request.form.get("product_id"))
    )

    if product.stock > 0:
        product.stock -= 1
        db.session.commit()
        flash("Stock reducido", "warning")

    return redirect(url_for("stock_page"))


# Agrega un color a los colores disponibles para una prenda (SOLO ADMIN)
@app.route("/stock/add_color", methods=["POST"])
@admin_only
def add_color():

    clothes = db.get_or_404(
        Clothes,
        int(request.form.get("clothes_id"))
    )

    hex_color = request.form.get("color_value")

    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    color = Color.query.filter_by(
        red=r, green=g, blue=b
    ).first()

    if not color:
        color = Color(red=r, green=g, blue=b)
        db.session.add(color)
        db.session.flush()

    exists = Product.query.filter_by(
        clothes_id=clothes.id,
        color_id=color.id
    ).first()

    if exists:
        flash("Ese color ya existe", "warning")
        return redirect(url_for("stock_page"))

    for size in Size.query.all():
        db.session.add(
            Product(
                clothes=clothes,
                color=color,
                size=size,
                stock=0
            )
        )

    db.session.commit()
    flash("Color agregado correctamente", "success")

    return redirect(url_for("stock_page"))


# Crea una orden de stock con la cantidad de productos que ingreso el usuario (SOLO ADMIN)
@app.route("/stock/order", methods=["POST"])
@admin_only
def stock_order():

    data = request.get_json()

    if not data or "items" not in data:
        return jsonify(success=False, error="Datos inválidos")

    try:

        stock_order = Stock_order(total=0)
        db.session.add(stock_order)

        total = 0

        for item in data["items"]:

            product = db.get_or_404(
                Product,
                item["product_id"]
            )

            amount = int(item["amount"])

            if amount <= 0:
                continue

            sop = Stock_order_product(
                stock_order=stock_order,
                product=product,
                amount=amount,
                price=product.clothes.price
            )

            product.stock += amount
            total += amount * product.clothes.price

            db.session.add(sop)

        stock_order.total = total
        db.session.commit()

        return jsonify(success=True)

    except Exception:
        db.session.rollback()
        return jsonify(success=False, error="Error al ingresar orden")


# Muestra productos en stock, permite ingresar ordenes de stock, quitar stock, agregar productos
# y discontinuar/activar productos (SOLO ADMIN)
@app.route('/stock')
@admin_only
def stock_page():

    clothes_list = (
        Clothes.query
        .options(
            joinedload(Clothes.brand),
            joinedload(Clothes.clothing_type),
            joinedload(Clothes.products)
                .joinedload(Product.size),
            joinedload(Clothes.products)
                .joinedload(Product.color)
        )
        .all()
    )

    for c in clothes_list:
        c.products.sort(key=lambda p: p.size.name)

    return render_template(
        "stock.html",
        clothes_list=clothes_list
    )


# Cambia entre discontinuar/activar en un producto (SOLO ADMIN)
@app.route("/stock/toggle/<int:clothes_id>", methods=["POST"])
@admin_only
def toggle_discontinued(clothes_id):
    clothes = db.get_or_404(Clothes, clothes_id)

    clothes.discontinued = not clothes.discontinued
    db.session.commit()

    return redirect(url_for("stock_page"))


# Agrega producto (SOLO ADMIN)
@app.route('/stock/nuevo', methods=["GET", "POST"])
@admin_only
def new_product_page():
    form = NuevoClothesForm()

    # cargar clothing types existentes
    form.clothing_type.choices = [
        (ct.id, ct.name) for ct in Clothing_type.query.all()
    ]

    if form.validate_on_submit():

        # Brand única
        brand = Brand.query.first()

        # convertir color HEX a RGB
        hex_color = form.color.data.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        color = Color(red=r, green=g, blue=b)
        db.session.add(color)
        db.session.flush()  # obtener ID sin commit

        # IMAGEN
        image_filename = None
        image_path = None

        if form.image.data:
            image_filename = Save_and_resize_image(
                form.image.data,
                app.config["UPLOAD_FOLDER"]
            )
            image_path = f"/static/uploads/{image_filename}" 

        # CLOTHES
        clothes = Clothes(
            name=form.name.data,
            price=form.price.data,
            brand=brand,
            clothing_type_id=form.clothing_type.data,
            image_filename=image_filename,
            image_path=image_path
        )

        db.session.add(clothes)
        db.session.flush()

        # crear Product por cada Size
        sizes = Size.query.all()

        for size in sizes:
            product = Product(
                clothes=clothes,
                size=size,
                color=color,
                stock=0
            )
            db.session.add(product)

        db.session.commit()

        flash("Producto creado correctamente", "success")
        return redirect(url_for("stock_page"))

    return render_template("nuevo_producto.html", form=form)


# Historial de órdenes de stock (SOLO ADMIN)
@app.route("/stock/orders")
@admin_only
def stock_orders_page():

    stock_orders = (
        Stock_order.query
        .options(
            joinedload(Stock_order.stock_order_products)
            .joinedload(Stock_order_product.product)
            .joinedload(Product.clothes)
            .joinedload(Clothes.brand),

            joinedload(Stock_order.stock_order_products)
            .joinedload(Stock_order_product.product)
            .joinedload(Product.size),

            joinedload(Stock_order.stock_order_products)
            .joinedload(Stock_order_product.product)
            .joinedload(Product.color),
        )
        .order_by(Stock_order.id.desc())
        .all()
    )

    return render_template(
        "stock_orders.html",
        stock_orders=stock_orders
    )



# Muestra graficos de ganancias en el tiempo, productos vendidos por prenda y por talle, con filtros disponibles
@app.route('/analytics', methods=["GET"])
@admin_only
def analytics_page():

    clothing_types = (
        Clothing_type.query
        .order_by(Clothing_type.name)
        .all()
    )

    # meses disponibles
    months_query = (
        db.session.query(
            extract("year", User_order.created_at),
            extract("month", User_order.created_at)
        )
        .filter(User_order.status == "paid")
        .distinct()
        .order_by(
            extract("year", User_order.created_at).desc(),
            extract("month", User_order.created_at).desc()
        )
        .all()
    )

    meses = []
    meses_espanol = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre"
}

    for y, m in months_query:
        fecha = datetime(int(y), int(m), 1)
        meses.append({
            "value": f"{int(y)}-{int(m)}",
            "label": f"{meses_espanol[int(m)]} {int(y)}"
        })

    return render_template(
        "analytics.html",
        clothing_types=clothing_types,
        meses=meses
    )


# Crea los graficos de analytics_page
@app.route('/analytics/data', methods=["GET"])
@admin_only
def analytics_data():

    month_year = request.args.get("month_year")
    clothing_type_id = request.args.get("clothing_type_id", type=int)

    year = None
    month = None

    if month_year:
        year, month = month_year.split("-")
        year = int(year)
        month = int(month)

    # =====================
    # Revenue
    # =====================

    revenue_query = (
        db.session.query(
            func.date(User_order.created_at),
            func.sum(Order_product.price * Order_product.amount)
        )
        .join(Order_product)
        .filter(User_order.status == "paid")
    )

    if year:
        revenue_query = revenue_query.filter(
            extract("year", User_order.created_at) == year,
            extract("month", User_order.created_at) == month
        )

    revenue_query = revenue_query.group_by(
        func.date(User_order.created_at)
    ).order_by(func.date(User_order.created_at)).all()

    revenue_data = {
        "labels":[str(r[0]) for r in revenue_query],
        "values":[float(r[1]) for r in revenue_query]
    }

    # =====================
    # BASE SALES QUERY
    # =====================

    sales_query = (
        db.session.query(Order_product)
        .join(User_order)
        .join(Product)
        .join(Clothes)
        .filter(User_order.status == "paid")
    )

    if year:
        sales_query = sales_query.filter(
            extract("year", User_order.created_at)==year,
            extract("month", User_order.created_at)==month
        )

    if clothing_type_id:
        sales_query = sales_query.filter(
            Clothes.clothing_type_id == clothing_type_id
        )

    sales = sales_query.all()

    # =====================
    # Clothes Pie
    # =====================

    clothes_counter = {}

    for op in sales:
        clothes_counter[op.clothes_name] = (
                clothes_counter.get(op.clothes_name, 0)
                + op.amount
        )

    # Ordenar por cantidad descendente
    sorted_clothes = sorted(
        clothes_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    top_5 = sorted_clothes[:5]
    others = sorted_clothes[5:]

    labels = [item[0] for item in top_5]
    values = [item[1] for item in top_5]

    # Si hay más de 5 productos, agrupar el resto
    if others:
        otros_total = sum(item[1] for item in others)
        labels.append("Otros")
        values.append(otros_total)

    clothes_data = {
        "labels": labels,
        "values": values
    }

    # =====================
    # Size Pie
    # =====================

    size_counter = {}

    for op in sales:
        size_counter[op.size_name] = (
            size_counter.get(op.size_name,0)
            + op.amount
        )

    size_data = {
        "labels":list(size_counter.keys()),
        "values":list(size_counter.values())
    }


    return jsonify({
        "revenue":revenue_data,
        "clothes":clothes_data,
        "sizes":size_data,

    })


# Plan de reorden de stock
@app.route("/analytics/reorder_plan")
@admin_only
def reorder_plan_page():

    results = generate_restock_recommendations()

    return render_template(
        "reorder.html",
        results=results
    )




if __name__ == "__main__":
    #app.run(debug=False, port=5001)
    app.run(debug=False)
