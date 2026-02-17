import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.linear_model import LinearRegression

from extensions import db
from tables.models import (
    Order_product,
    User_order,
    Product,
    Clothes,
    Restock_recommendation
)

# =========================================
# CREA EL DATASET DE VENTAS MENSUALES
# =========================================

def build_sales_dataset():

    query = (
        db.session.query(
            Order_product.product_id,
            Order_product.amount,
            User_order.created_at
        )
        .join(User_order)
        .join(Product)
        .join(Clothes)
        .filter(Clothes.discontinued == False)
        .all()
    )

    if not query:
        return pd.DataFrame()

    df = pd.DataFrame(query, columns=[
        "product_id",
        "amount",
        "created_at"
    ])

    df["date"] = pd.to_datetime(df["created_at"]).dt.to_period("M")


    # Agrupa ventas por mes
    monthly = (
        df.groupby(["product_id", "date"])["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "sold_qty"})
    )

    # Rellenar meses faltantes
    filled = []

    for product_id, group in monthly.groupby("product_id"):

        start = group["date"].min()
        end = datetime.now().strftime("%Y-%m")
        end = pd.Period(end, freq="M")

        full_range = pd.period_range(start, end, freq="M")

        group = (
            group.set_index("date")
            .reindex(full_range)
            .fillna(0)
            .rename_axis("date")
            .reset_index()
        )

        group["product_id"] = product_id
        filled.append(group)

    return pd.concat(filled)


# =========================================
# CREAR FEATURES
# =========================================

def build_features(df):

    frames = []

    for product_id, group in df.groupby("product_id"):

        group = group.sort_values("date")

        # Variables predictivas

        # Enumera mes a mes desde el primero que aparece
        group["time_index"] = range(len(group))
        # Mes anterior
        group["lag1"] = group["sold_qty"].shift(1)
        # 2 Meses atras
        group["lag2"] = group["sold_qty"].shift(2)
        # Promedio movil para suavizar ruido
        group["avg2"] = group["sold_qty"].rolling(2).mean()

        # reemplazar NaN por 0 para no perder productos
        group = group.fillna(0)

        frames.append(group)

    return pd.concat(frames)


# =========================================
# PREDECIR DEMANDA
# =========================================

def predict_demand(group):

    n = len(group)

    # > 4 Meses, regresion lineal
    if n >= 4:

        X = group[["time_index", "lag1", "lag2", "avg2"]]
        y = group["sold_qty"]

        model = LinearRegression()
        model.fit(X, y)

        last = group.iloc[-1]

        features = np.array([[
            last["time_index"] + 1,
            last["lag1"],
            last["lag2"],
            last["avg2"]
        ]])

        return max(0, int(model.predict(features)[0]))

    # 2-3 meses, promedio ponderado con mayor peso al mes mas reciente
    if n >= 2:

        weights = np.linspace(1, 2, n)
        return int(np.average(group["sold_qty"], weights=weights))

    # 1 solo dato, repite dato del mes anterior
    if n == 1:
        return int(group.iloc[-1]["sold_qty"])

    # Si no hay datos anteriores, no puede predecir y devuelve 0
    return 0

# =========================================
# RESTOCK CALCULATION
# =========================================

def generate_restock_recommendations():

    df = build_sales_dataset()

    if df.empty:
        return []

    features_df = build_features(df)

    Restock_recommendation.query.delete()

    results = []

    for product_id, group in features_df.groupby("product_id"):

        product = Product.query.get(product_id)

        if not product:
            continue

        if product.clothes.discontinued:
            continue

        predicted = predict_demand(group)

        # Usa la desviación estandar para calcular el stock de seguridad
        std = group["sold_qty"].std()
        if np.isnan(std):
            std = 0

        safety = int(std * 1.65)

        restock = max(
            0,
            predicted + safety - product.stock
        )

        rec = Restock_recommendation(
            product_id=product.id,
            predicted_demand=predicted,
            safety_stock=safety,
            suggested_restock=restock
        )

        db.session.add(rec)

        results.append({
            "product": product,
            "predicted": predicted,
            "safety": safety,
            "restock": restock
        })

    db.session.commit()

    return sorted(
        results,
        key=lambda x: (
            x["product"].clothes.name,
            x["product"].color.id,
            x["product"].size.name
        )
    )
