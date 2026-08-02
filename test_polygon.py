"""
ملف اختباري مؤقت -- يتأكد إن Polygon /v3/reference/splits يشتغل صح
قبل ما نبنيه بشكل نهائي بمصادر البيانات. يُحذف بعد التأكد.
"""

import streamlit as st
import requests

st.title("🧪 اختبار Polygon Splits API")

api_key = st.secrets["POLYGON_API_KEY"]

# نجرب سهم معروف عمل reverse split مؤخرًا كمثال
test_ticker = st.text_input("رمز السهم للاختبار", value="RLYB")

if st.button("اختبر"):
    resp = requests.get(
        "https://api.polygon.io/v3/reference/splits",
        params={
            "ticker": test_ticker,
            "reverse_split": "true",
            "apiKey": api_key,
        },
        timeout=15,
    )
    st.write("Status Code:", resp.status_code)
    st.json(resp.json())
