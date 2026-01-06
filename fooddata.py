import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase

st.set_page_config(page_title="Food Nutrition Scanner", layout="centered")
st.title("Food Nutrition Scanner (Live Camera)")

barcode = st.session_state.get("barcode", None)

class BarcodeScanner(VideoProcessorBase):
    def __init__(self):
        self.detector = cv2.barcode.BarcodeDetector()

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")

        result = self.detector.detectAndDecode(img)
        if isinstance(result, tuple):
            decoded = result[0]
        else:
            decoded = result

        if decoded:
            st.session_state["barcode"] = decoded.strip()

        return frame

webrtc_streamer(
    key="scanner",
    video_processor_factory=BarcodeScanner,
    media_stream_constraints={"video": True, "audio": False},
)

if "barcode" in st.session_state:
    st.success(f"Detected barcode: {st.session_state['barcode']}")
    barcode = st.session_state["barcode"]

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

        st.header(product.get("product_name", "Unknown Product"))
        st.subheader(f"Nutrition Grade: {product.get('nutrition_grades', 'N/A').upper()}")

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
