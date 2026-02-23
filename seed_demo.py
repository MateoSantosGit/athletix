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
    Stock_order,
    Stock_order_product
)

from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random


def run_seed_demo():

    with app.app_context():

        brand = Brand.query.filter_by(name="Athletix").first()
        types = Clothing_type.query.all()
        sizes = Size.query.all()

        # -----------------------------
        # COLORES
        # -----------------------------
        palette = [
            (0, 0, 0),
            (255, 255, 255),
            (30, 30, 120),
            (120, 120, 120),
            (180, 30, 30),
            (20, 120, 60),
            (90, 40, 140),
            (200, 150, 50),
            (50, 150, 200)
        ]

        colors = []

        for r, g, b in palette:
            c = Color.query.filter_by(red=r, green=g, blue=b).first()
            if not c:
                c = Color(red=r, green=g, blue=b)
                db.session.add(c)
            colors.append(c)

        db.session.commit()

        # -----------------------------
        # 30 PRENDAS
        # -----------------------------
        clothes_data = [
            # REMERAS (0)
            ["Remera Performance DryFit", 0, "remera1.jpg"],
            ["Remera Training Fit", 0, "remera2.jpg"],
            ["Remera Oversize Street", 0, "remera3.jpg"],
            ["Remera Compresión", 0, "remera4.jpg"],
            ["Remera UltraLight", 0, "remera5.jpg"],
            ["Remera Urban Fit", 0, "remera6.jpg"],
            ["Remera Essential", 0, "remera7.jpg"],

            # PANTALONES (1)
            ["Pantalón Jogger Flex", 1, "pantalon1.jpg"],
            ["Pantalón Training Slim", 1, "pantalon2.jpg"],
            ["Pantalón Cargo Sport", 1, "pantalon3.jpg"],
            ["Pantalón Running Pro", 1, "pantalon4.jpg"],
            ["Pantalón Algodón Premium", 1, "pantalon5.jpg"],
            ["Pantalón Térmico", 1, "pantalon6.jpg"],
            ["Pantalón Motion", 1, "jogging.jpeg"],

            # CAMPERAS (2)
            ["Campera Softshell Urban", 2, "campera1.jpg"],
            ["Campera Impermeable Active", 2, "campera2.jpg"],
            ["Campera Core", 2, "campera3.jpg"],
            ["Campera Rompeviento Light", 2, "campera4.jpg"],
            ["Campera Half Zip", 2, "campera5.jpg"],
            ["Campera Polar Trek", 2, "campera6.jpg"],
            ["Campera Expedition", 2, "campera7.jpg"],
            ["Campera Aero", 2, "campera_nautica.jpg"],
            ["Campera Performance Zip", 2, "campera_pro.jpg"],

            # SHORTS (3)
            ["Short Pro Runner", 3, "short1.jpg"],
            ["Short Essentials", 3, "short2.jpg"],
            ["Short Outdoor Tech", 3, "short3.jpg"],
            ["Short Competición Elite", 3, "short4.jpg"],
            ["Short Básico Deportivo", 3, "short5.jpg"],
            ["Short Trail", 3, "short6.jpg"],
            ["Short Dynamic", 3, "short.jpg"]
        ]

        clothes_objects = []

        for name, tipos, imagen in clothes_data:

            if Clothes.query.filter_by(name=name).first():
                continue

            price = random.randint(6000, 32000)

            c = Clothes(
                name=name,
                price=price,
                image_filename=imagen,  # ← agregás la imagen
                image_path=f"/static/uploads/{imagen}",
                brand=brand,
                clothing_type=types[tipos],
                discontinued=False
            )

            db.session.add(c)
            db.session.flush()
            clothes_objects.append(c)

        db.session.commit()

        # -----------------------------
        # PRODUCTS (colores + 6 talles)
        # -----------------------------
        for clothes in Clothes.query.all():

            selected_colors = random.sample(colors, k=random.randint(2, 4))

            for color in selected_colors:
                for size in sizes:

                    if not Product.query.filter_by(
                        clothes_id=clothes.id,
                        size_id=size.id,
                        color_id=color.id
                    ).first():

                        stock = random.randint(10, 25)

                        p = Product(
                            clothes=clothes,
                            size=size,
                            color=color,
                            stock=stock
                        )

                        db.session.add(p)

        db.session.commit()

        products = Product.query.all()

        # -----------------------------
        # 120 CLIENTES
        # -----------------------------
        users = []

        for i in range(1, 501):

            username = f"cliente{i}"

            u = User.query.filter_by(username=username).first()

            if not u:
                u = User(
                    username=username,
                    password=generate_password_hash(
                        "clave123",
                        method="pbkdf2:sha256",
                        salt_length=8
                    ),
                    email=f"cliente{i}@mail.com",
                    is_admin=False
                )
                db.session.add(u)
                db.session.flush()

            users.append(u)

        db.session.commit()

        # -----------------------------
        # ÓRDENES REALISTAS
        # -----------------------------
        start_date = datetime(2025, 3, 1)
        end_date = datetime(2026, 2, 1)

        current = start_date

        while current <= end_date:

            seasonal_factor = 1.0

            if current.month in [6, 7]:
                seasonal_factor = 1.9
            if current.month in [11, 12]:
                seasonal_factor = 2.4

            for user in users:

                if random.random() > 0.2 * seasonal_factor:
                    continue

                order = User_order(
                    user=user,
                    total=0,
                    status="paid",
                    created_at=current + timedelta(days=random.randint(0, 6)),
                    expires_at=current + timedelta(days=1)
                )

                db.session.add(order)
                db.session.flush()

                total = 0

                for _ in range(random.randint(1, 15)):

                    product = random.choice(products)
                    amount = random.randint(1, 3)

                    op = Order_product(
                        user_order=order,
                        product=product,
                        amount=amount,
                        price=product.clothes.price,
                        clothes_name=product.clothes.name,
                        size_name=product.size.name
                    )

                    db.session.add(op)
                    total += product.clothes.price * amount

                order.total = total

            current += timedelta(days=random.randint(1, 7))

        db.session.commit()

        # -----------------------------
        # MUCHAS STOCK ORDERS
        # -----------------------------
        for _ in range(180):

            stock_order = Stock_order(
                total=0,
                created_at=datetime(2025, 1, 1) + timedelta(days=random.randint(0, 420))
            )

            db.session.add(stock_order)
            db.session.flush()

            total = 0

            for _ in range(random.randint(3, 10)):

                product = random.choice(products)
                amount = random.randint(10, 80)
                cost_price = random.randint(3000, 15000)

                sop = Stock_order_product(
                    stock_order=stock_order,
                    product=product,
                    amount=amount,
                    price=cost_price
                )

                db.session.add(sop)

                total += cost_price * amount



            stock_order.total = total

        db.session.commit()

        print("🚀 Seed demo grande generado correctamente")


if __name__ == "__main__":
    run_seed_demo()