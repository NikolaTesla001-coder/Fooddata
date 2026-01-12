import streamlit as st
import requests
import pandas as pd
from PIL import Image
import google.generativeai as genai
import json
import re

# ---------------- Page Config ----------------
st.set_page_config(page_title="Food Nutrition Analyzer", layout="centered")
st.title("Food Nutrition Analyzer")

# ---------------- Gemini Setup ----------------
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

# ---------------- Helpers ----------------
def extract_json(text):
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    return json.loads(match.group())

# ---------------- Tabs ----------------
tab1, tab2 = st.tabs(["Nutrition Analyzer", "Object Counter"])

# ============================================================
# TAB 1 — Nutrition Analyzer (UNCHANGED)
# ============================================================
with tab1:
    barcode = st.text_input("Enter Barcode", placeholder="e.g. 0011110119681")

    if st.button("Fetch Product Info") and barcode:

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

            st.header(product.get("product_name", "Unknown Product"))
            grade = product.get("nutrition_grades", "N/A").upper()
            st.subheader(f"Nutrition Grade: {grade}")

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

            nutriscore = product.get("nutriscore_data", {})
            components = nutriscore.get("components", {})

            def build_df(items, kind):
                rows = []
                for c in items:
                    rows.append([
                        c.get("id").replace("_", " ").title(),
                        c.get("value"),
                        c.get("unit"),
                        c.get("points"),
                        c.get("points_max"),
                        kind,
                    ])
                return pd.DataFrame(rows, columns=["Component", "Value", "Unit", "Points", "Max", "Type"])

            neg_df = build_df(components.get("negative", []), "Negative")
            pos_df = build_df(components.get("positive", []), "Positive")

            df_components = pd.concat([neg_df, pos_df], ignore_index=True)
            st.subheader("Nutri-Score Components")
            st.dataframe(df_components, use_container_width=True)

            summary = pd.DataFrame([
                ("Final Score", nutriscore.get("score")),
                ("Negative Points", nutriscore.get("negative_points")),
                ("Positive Points", nutriscore.get("positive_points")),
            ], columns=["Metric", "Value"])

            st.subheader("Nutri-Score Summary")
            st.table(summary)

            with pd.ExcelWriter("nutrition_report.xlsx", engine="openpyxl") as writer:
                df_nutrition.to_excel(writer, sheet_name="Nutrition Facts", index=False)
                df_components.to_excel(writer, sheet_name="NutriScore Breakdown", index=False)
                summary.to_excel(writer, sheet_name="Summary", index=False)

            with open("nutrition_report.xlsx", "rb") as f:
                st.download_button(
                    "Download Excel Report",
                    f,
                    file_name="nutrition_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# ============================================================
# TAB 2 — Object Counter (JSON Safe)
# ============================================================
with tab2:
    st.subheader("Upload an image to count objects")

    uploaded_image = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"], key="counter")

    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Uploaded image", use_container_width=True)

        if st.button("Count Objects"):
            with st.spinner("Analyzing image..."):

                prompt = """
You are a computer vision system.
Return ONLY valid JSON. Do not use markdown. Do not use backticks. Do not explain.

Detect all individual objects in the image.
Return:
{
  "count": number
  
}
"""

                response = model.generate_content(
                    [prompt, image],
                    generation_config={"temperature": 0.1}
                )

                parsed = extract_json(response.text)

                if parsed:
                    st.subheader("Detection Result")
                    st.metric(label="Count", value=int(parsed["count"]))
        
                else:
                    st.error("Model did not return valid JSON.")
                    st.text(response.text)
