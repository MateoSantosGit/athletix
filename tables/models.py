from extensions import db
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey, Boolean, DateTime, Float
from datetime import date, datetime
from sqlalchemy.sql import expression
from flask_login import UserMixin



# Clase marca de producto
class Brand(db.Model):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    # one to many
    clothes: Mapped[list["Clothes"]] = relationship(
        "Clothes",
        back_populates="brand",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase producto en carrito
class Cart_item(db.Model):
    __tablename__ = "cart_items"
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='unique_user_product'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[int] = mapped_column(Integer)

    # many to one
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    user: Mapped["User"] = relationship("User", back_populates="cart_items")

    # many to one
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False
    )
    product: Mapped["Product"] = relationship("Product", back_populates="cart_items")


####################################################################

# Clase prenda
class Clothes(db.Model):
    __tablename__ = "clothes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price: Mapped[float] = mapped_column(Float)
    name: Mapped[str] = mapped_column(String(100))

    image_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=True)

    # NUEVO CAMPO
    discontinued: Mapped[bool] = mapped_column(
        Boolean,
        default=False,  # default en Python
        server_default=expression.false(),  # default en DB
        nullable=False
    )

    # many to one
    brand_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False
    )
    brand: Mapped["Brand"] = relationship("Brand", back_populates="clothes")

    # many to one
    clothing_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("clothing_types.id", ondelete="CASCADE"),
        nullable=False
    )
    clothing_type: Mapped["Clothing_type"] = relationship(
        "Clothing_type",
        back_populates="clothes"
    )


    # one to many
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="clothes",
        cascade="all, delete-orphan"
    )

    @property
    def image_url(self):
        """Devuelve la URL completa de la imagen"""
        if self.image_filename:
            # Dependiendo de cómo configures las rutas
            return f"/static/uploads/{self.image_filename}"
        return "/static/not-found.jpg"  # Imagen por defecto


####################################################################

class Clothing_type(db.Model):
    __tablename__ = "clothing_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # one to many
    clothes: Mapped[list["Clothes"]] = relationship(
        "Clothes",
        back_populates="clothing_type",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase color del producto
class Color(db.Model):
    __tablename__ = "colors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    red: Mapped[int] = mapped_column(Integer)
    green: Mapped[int] = mapped_column(Integer)
    blue: Mapped[int] = mapped_column(Integer)

    # one to many
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="color",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase productos en la orden del usuario
class Order_product(db.Model):
    __tablename__ = "order_products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clothes_name: Mapped[str] = mapped_column(String(100), nullable=False)
    size_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)

    # many to one
    user_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_orders.id", ondelete="CASCADE"),
        nullable=False
    )
    user_order: Mapped["User_order"] = relationship(
        "User_order",
        back_populates="order_products"
    )

    # many to one
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False
    )
    product: Mapped["Product"] = relationship("Product", back_populates="order_products")


####################################################################


# Clase producto completo
class Product(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock: Mapped[int] = mapped_column(Integer)

    # many to one
    clothes_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("clothes.id", ondelete="CASCADE"),
        nullable=False
    )
    clothes: Mapped["Clothes"] = relationship("Clothes", back_populates="products")

    # many to one
    size_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sizes.id", ondelete="CASCADE"),
        nullable=False
    )
    size: Mapped["Size"] = relationship("Size", back_populates="products")

    # many to one
    color_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("colors.id", ondelete="CASCADE"),
        nullable=False
    )
    color: Mapped["Color"] = relationship("Color", back_populates="products")

    # one to many
    order_products: Mapped[list["Order_product"]] = relationship(
        "Order_product",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    # one to many
    cart_items: Mapped[list["Cart_item"]] = relationship(
        "Cart_item",
        back_populates="product",
        cascade="all, delete-orphan"
    )

    stock_order_products: Mapped[list["Stock_order_product"]] = relationship(
        "Stock_order_product",
        back_populates="product",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase tamano del producto
class Size(db.Model):
    __tablename__ = "sizes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    # one to many
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="size",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase orden de stock que ingresa
class Stock_order(db.Model):
    __tablename__ = "stock_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    # one to many
    stock_order_products: Mapped[list["Stock_order_product"]] = relationship(
        "Stock_order_product",
        back_populates="stock_order",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase productos en la orden de stock
class Stock_order_product(db.Model):
    __tablename__ = "stock_order_products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)

    # many to one
    stock_order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stock_orders.id", ondelete="CASCADE"),
        nullable=False
    )
    stock_order: Mapped["Stock_order"] = relationship("Stock_order", back_populates="stock_order_products")

    # many to one
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False
    )
    product: Mapped["Product"] = relationship("Product", back_populates="stock_order_products")


####################################################################

# Clase usuario
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean)

    # one to many
    user_orders: Mapped[list["User_order"]] = relationship(
        "User_order",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # one to many
    cart_items: Mapped[list["Cart_item"]] = relationship(
        "Cart_item",
        back_populates="user",
        cascade="all, delete-orphan"
    )


####################################################################

# Clase orden de usuario
class User_order(db.Model):
    __tablename__ = "user_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total: Mapped[float] = mapped_column(Float)
    mp_preference_id: Mapped[str] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    order_number: Mapped[str] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    # one to many
    order_products: Mapped[list["Order_product"]] = relationship(
        "Order_product",
        back_populates="user_order",
        cascade="all, delete-orphan"
    )


    # many to one
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    user: Mapped["User"] = relationship("User", back_populates="user_orders")



####################################################################

# PARA PREDICCION
class Restock_recommendation(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    predicted_demand = db.Column(db.Integer, nullable=False)
    safety_stock = db.Column(db.Integer, nullable=False)
    suggested_restock = db.Column(db.Integer, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
