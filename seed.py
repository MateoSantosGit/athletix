from main import app
from extensions import db
from tables.models import Clothing_type, Size, Brand, User
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv


def run_seed():

    load_dotenv()

    with app.app_context():

        # -----------------------------
        # CLOTHING TYPES
        # -----------------------------
        if not Clothing_type.query.first():
            db.session.add_all([
                Clothing_type(name="Remera"),
                Clothing_type(name="Pantalón"),
                Clothing_type(name="Campera"),
                Clothing_type(name="Short"),
            ])

        # -----------------------------
        # SIZES
        # -----------------------------
        if not Size.query.first():
            db.session.add_all([
                Size(name="XS"),
                Size(name="S"),
                Size(name="M"),
                Size(name="L"),
                Size(name="XL"),
                Size(name="XXL")
            ])

        # -----------------------------
        # BRAND
        # -----------------------------
        if not Brand.query.filter_by(name="Athletix").first():
            db.session.add(Brand(name="Athletix"))

        # -----------------------------
        # ADMIN
        # -----------------------------
        if not User.query.filter_by(username=os.getenv("ADMIN_NAME")).first():

            admin = User(
                username=os.getenv("ADMIN_NAME"),
                password=generate_password_hash(
                    os.getenv("ADMIN_PASSWORD"),
                    method="pbkdf2:sha256",
                    salt_length=8
                ),
                email="admin@athletix.com",
                is_admin=True
            )

            db.session.add(admin)

        db.session.commit()
        print("✅ Seed estructural completado")


if __name__ == "__main__":
    run_seed()