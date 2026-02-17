from main import app
from extensions import db
from tables.models import (
    Clothing_type,
    Size,
    Brand,
    User,
    Clothes,
    Color,
    Product,
    User_order,
    Order_product,
)

from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv

load_dotenv()

UPLOAD_IMAGE = "4f65c450f4994b9d8f6e57e8fd514cc1.jpg"

with app.app_context():

    # ---------------------------------
    # BASE DATA
    # ---------------------------------

    if not Clothing_type.query.first():
        db.session.add_all([
            Clothing_type(name="Remera"),
            Clothing_type(name="Pantalón"),
            Clothing_type(name="Campera"),
            Clothing_type(name="Short")
        ])

    if not Size.query.first():
        db.session.add_all([
            Size(name="XS"),
            Size(name="S"),
            Size(name="M"),
            Size(name="L"),
            Size(name="XL"),
            Size(name="XXL")
        ])

    if not Brand.query.filter_by(name="Athletix").first():
        db.session.add(Brand(name="Athletix"))

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password=generate_password_hash(
                os.getenv("ADMIN_PASSWORD"),
                method="pbkdf2:sha256",
                salt_length=8
            ),
            is_admin=True
        )
        db.session.add(admin)

    db.session.commit()

    brand = Brand.query.filter_by(name="Athletix").first()
    types = Clothing_type.query.all()
    sizes = Size.query.all()

    # ---------------------------------
    # COLORES
    # ---------------------------------

    color1 = Color.query.filter_by(red=0, green=0, blue=0).first()
    if not color1:
        color1 = Color(red=0, green=0, blue=0)
        db.session.add(color1)

    color2 = Color.query.filter_by(red=255, green=0, blue=0).first()
    if not color2:
        color2 = Color(red=255, green=0, blue=0)
        db.session.add(color2)

    db.session.commit()

    # ---------------------------------
    # CLOTHES
    # ---------------------------------

    clothes_list = []

    if not Clothes.query.first():

        sample_clothes = [
            ("Remera Básica", 1500),
            ("Jean 511", 3000),
            ("Campera Pro", 7000),
            ("Short Runner", 2000),
        ]

        for i, (name, price) in enumerate(sample_clothes):

            c = Clothes(
                name=name,
                price=price,
                image_filename=UPLOAD_IMAGE,
                image_path=f"/static/uploads/{UPLOAD_IMAGE}",
                brand=brand,
                clothing_type=types[i % len(types)],
                discontinued=False
            )

            db.session.add(c)
            clothes_list.append(c)

        db.session.commit()

    else:
        clothes_list = Clothes.query.all()

    # ---------------------------------
    # PRODUCTS
    # ---------------------------------

    if not Product.query.first():

        for clothes in clothes_list:

            for size in sizes:

                p = Product(
                    clothes=clothes,
                    size=size,
                    color=color1,
                    stock=random.randint(0, 15)
                )

                db.session.add(p)

        db.session.commit()

    products = Product.query.all()

    # ---------------------------------
    # USERS
    # ---------------------------------

    users = []



    for i in range(1, 100):

        username = f"user{i}"

        u = User.query.filter_by(username=username).first()

        if not u:
            u = User(
                username=username,
                password=generate_password_hash(
                    "test123",
                    method="pbkdf2:sha256",
                    salt_length=8
                ),
                is_admin=False
            )
            db.session.add(u)
            db.session.flush()

        users.append(u)

    db.session.commit()

    # ---------------------------------
    # ORDERS HISTÓRICAS
    # ---------------------------------

    if not User_order.query.first():

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2026, 2, 10)

        current = start_date

        while current <= end_date:

            for user in users:

                if random.random() < 0.1:
                    continue

                order = User_order(
                    user=user,
                    total=0,
                    status="paid",
                    created_at=current,
                    expires_at=current + timedelta(days=1)
                )

                db.session.add(order)
                db.session.flush()

                total = 0

                for _ in range(random.randint(1, 3)):

                    product = random.choice(products)
                    amount = random.randint(1, 3)
                    price = product.clothes.price

                    op = Order_product(
                        user_order=order,
                        product=product,
                        amount=amount,
                        price=price,
                        clothes_name=product.clothes.name,
                        size_name=product.size.name
                    )

                    db.session.add(op)

                    total += price * amount

                order.total = total

            current += timedelta(days=10)

        db.session.commit()

    print("✅ Seed completado correctamente")
