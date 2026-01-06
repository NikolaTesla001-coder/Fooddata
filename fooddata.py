import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Food Nutrition Analyzer", layout="centered")
st.title("Food Nutrition Analyzer")

st.write("Enter the barcode (scan using your phone camera externally if needed).")

barcode = st.text_input("Enter Barcode", placeholder="e.g. 3017624010701")

# ---- Fetch product info ----
if barcode and st.button("Fetch Product Info"):

    url = (
        f"https://world.openfoodfacts.net/api/v2/product/{barcode}"
        "?fields=product_name,nutriscore_data,nutriments,nutrition_grades"
    )

    r = requests.get(url, timeout=10)
    data = r.json()

    if data.get("status") != 1:
        st.error("Product not found")
    else:
        product = data["product"]

        # ---------------- Header ----------------
        st.header(product.get("product_name", "Unknown Product"))
        st.subheader(f"Nutrition Grade: {product.get('nutrition_grades', 'N/A').upper()}")

        # ---------------- Nutrition Facts ----------------
        nutriments = product.get("nutriments", {})
        nutrition_rows = []

        for key, val in nutriments.items():
            if key.endswith("_100g"):
                base = key.replace("_100g", "")
                name = base.replace("-", " ").replace("_", " ").title()
                unit = nutriments.get(f"{base}_unit", "")
                nutrition_rows.append([name, round(val, 2), unit])

        df_nutrition = pd.DataFrame(nutrition_rows, columns=["Nutrient", "Per 100g", "Unit"])
        st.subheader("Nutrition Facts (per 100g)")
        st.dataframe(df_nutrition, use_container_width=True)

        # ---------------- Nutri-Score Breakdown ----------------
        nutriscore = product.get("nutriscore_data", {})
        components = nutriscore.get("components", {})

        def build_component_df(items, kind):
            rows = []
            for c in items:
                rows.append([
                    c.get("id", "").replace("_", " ").title(),
                    c.get("value"),
                    c.get("unit"),
                    c.get("points"),
                    c.get("points_max"),
                    kind,
                ])
            return pd.DataFrame(rows, columns=["Component", "Value", "Unit", "Points", "Max Points", "Type"])

        neg_df = build_component_df(components.get("negative", []), "Negative")
        pos_df = build_component_df(components.get("positive", []), "Positive")

        df_components = pd.concat([neg_df, pos_df], ignore_index=True)

        st.subheader("Nutri-Score Components")
        st.dataframe(df_components, use_container_width=True)

        # ---------------- Summary ----------------
        summary = pd.DataFrame([
            ("Final Score", nutriscore.get("score")),
            ("Negative Points", nutriscore.get("negative_points")),
            ("Positive Points", nutriscore.get("positive_points")),
        ], columns=["Metric", "Value"])

        st.subheader("Nutri-Score Summary")
        st.table(summary)
