import streamlit as st
import requests
import pandas as pd
from PIL import Image
import google.generativeai as genai
import json
import re
from io import BytesIO

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

        if "detect_count" in st.session_state:
              count=st.session_state.detect_count
            #   container=st.session_state.detect_type

        if data.get("status") != 1:
            st.error("Product not found")
        else:
            product = data["product"]
            st.header(product.get("product_name", "Unknown Product"))
            if "detect_count" in st.session_state:
             st.header(f'no of bottles:{st.session_state.detect_count}')
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
                ("Positive Points", nutriscore.get("positive_points")),
                ("Negative Points", nutriscore.get("negative_points")),
                ("Final Score", nutriscore.get("positive_points")-nutriscore.get("negative_points")),
            ], columns=["Metric", "Value"])



            excel_summary = pd.DataFrame([{
                "Product Name": product.get("product_name"),
                "Number": st.session_state.get("detect_count", 1),
                "Final Score":  nutriscore.get("positive_points", 0) - nutriscore.get("negative_points", 0)
            }])


            st.subheader("Nutri-Score Summary")
            st.table(summary)

            score=nutriscore.get("positive_points")-nutriscore.get("negative_points")
            if score>0:
                st.success("THE SELECTED FOOD ITEM IS HEALTHY")

            with pd.ExcelWriter("nutrition_report.xlsx", engine="openpyxl") as writer:
                excel_summary.to_excel(writer, sheet_name="Summary", index=False)

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
@st.cache_data(show_spinner=False)
def analyze_image_cached(image_bytes):
    image = Image.open(BytesIO(image_bytes))  

    prompt = """
You are a visual analysis system.

Step 1:
Identify the most frequently occurring distinct physical object type in the image.
Name it clearly (e.g., "jar", "bottle", "can").

Step 2:
Count the number of visible instances of that object type.

Rules:
- Objects must be visually similar in shape and purpose.
- Ignore packaging, containers, and background items.
- Do not guess hidden or occluded objects.
- Count conservatively.

Return ONLY valid JSON:
{
  "object_type": "string",
  "count": number
}
"""

    response = model.generate_content(
        [prompt, image],
        generation_config={"temperature": 0.1}
    )
    return response.text
with tab2:
    st.subheader("Upload an image to count objects")

    source = st.radio(
        "Choose input method",
        ["Upload", "Camera"],
        horizontal=True
    )

    uploaded_image = None

    if source == "Upload":
        uploaded_image = st.file_uploader(
            "Upload Image",
            type=["png", "jpg", "jpeg"],
            key="counter_upload"
        )

    elif source == "Camera":
        uploaded_image = st.camera_input(
            "Take a picture",
            key="counter_camera"
        )

    
    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Input image", use_container_width=True)

        img_bytes = uploaded_image.getvalue()
        img_hash = hash(img_bytes)

        if "last_hash" not in st.session_state or st.session_state.last_hash != img_hash:
            st.session_state.last_hash = img_hash
            st.session_state.analysis_done = False

        if st.button("Count Objects") and not st.session_state.get("analysis_done", False):
            with st.spinner("Analyzing image..."):
                raw_response = analyze_image_cached(img_bytes)

                parsed = extract_json(raw_response)

                if parsed and isinstance(parsed.get("count"), int):
                    st.subheader("Detection Result")
                    st.metric("Count", parsed["count"])
                    st.session_state.analysis_done = True

                    st.session_state.detect_count = parsed["count"]
                    st.session_state.detect_type = parsed["object_type"]

                else:
                    st.error("Model did not return valid JSON.")
                    st.text(raw_response)
                
                
