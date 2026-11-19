"""Professional API-connected Streamlit dashboard.
Run: .\\.venv\\Scripts\\python.exe -m streamlit run app_streamlit_api.py
"""
from datetime import datetime
import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="WeatherPulse | Weather Intelligence", page_icon="🌦️", layout="wide", initial_sidebar_state="expanded")

st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
.stApp{background:#f4f7fb}
[data-testid="stHeader"]{background:rgba(244,247,251,.92)}
[data-testid="stSidebar"]{background:#101d35}
[data-testid="stSidebar"] *{color:#edf3ff}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#1b2c4a;color:white;border-color:#344968}
[data-testid="stSidebar"] [data-testid="stButton"] button{border-radius:10px;border:1px solid #385477;background:#1d3558;color:white;font-weight:600}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{background:#4d8df7;border-color:#4d8df7}
.hero{background:linear-gradient(115deg,#142747,#234b78 58%,#3475a8);border-radius:18px;padding:26px 30px;color:white;margin:4px 0 22px;box-shadow:0 10px 28px rgba(23,54,91,.13)}
.hero-kicker{color:#c8dcf5;font-size:.78rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;margin-bottom:8px}
.hero-title{font-size:clamp(1.65rem,3vw,2.35rem);line-height:1.15;font-weight:800;margin:0}
.hero-subtitle{color:#d8e7f8;font-size:.95rem;margin-top:8px}
.section-heading{color:#172b49;font-size:1.18rem;font-weight:750;margin:8px 0 3px}
.section-subtitle{color:#718096;font-size:.84rem;margin-bottom:14px}
div[data-testid="stMetric"]{background:white;border:1px solid #e5ebf3;border-radius:14px;padding:15px 17px;box-shadow:0 3px 12px rgba(24,47,79,.035)}
div[data-testid="stMetricLabel"]{color:#64748b;font-weight:600}
div[data-testid="stMetricValue"]{color:#172b49;font-weight:750}
div[data-testid="stTabs"] button{font-weight:650}
div[data-testid="stDataFrame"]{border:1px solid #e5ebf3;border-radius:12px;overflow:hidden}
.status-pill{display:inline-block;border-radius:999px;padding:5px 11px;background:#e6f6ed;color:#18794e;font-size:.76rem;font-weight:700}
.muted{color:#718096;font-size:.82rem}
.empty-state{background:white;border:1px dashed #cbd5e1;border-radius:14px;padding:22px;color:#64748b;text-align:center}
footer,#MainMenu{visibility:hidden}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {"weather_data": None, "forecast_data": None, "alert_data": None, "weather_history": None, "alert_history": None, "last_updated": None, "last_city": None}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def api_get(base_url, endpoint, params=None):
    try:
        response = requests.get(f"{base_url.rstrip('/')}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "Could not connect to FastAPI. If this dashboard is deployed, set "
            "API_BASE_URL in Streamlit app Secrets to your public backend URL "
            "(for example, https://your-service.onrender.com). "
            "If running locally, start FastAPI in a separate terminal."
        )
    except requests.exceptions.Timeout:
        st.error("The API request timed out. Please try again.")
    except requests.exceptions.HTTPError:
        try:
            detail = response.json().get("detail", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        st.error(f"API error ({response.status_code}): {detail}")
    except requests.exceptions.RequestException as error:
        st.error(f"Request failed: {error}")
    except ValueError:
        st.error("The API returned a response that was not valid JSON.")
    return None


def load_weather(base_url, city_name, provider_name):
    params = {"city": city_name, "provider": provider_name}
    with st.spinner(f"Loading weather information for {city_name}..."):
        current = api_get(base_url, "/weather/current", params)
        forecast = api_get(base_url, "/weather/forecast", params)
        alerts = api_get(base_url, "/alerts", params)
    if current is None:
        return False
    st.session_state.weather_data = current
    st.session_state.forecast_data = forecast
    st.session_state.alert_data = alerts
    st.session_state.last_updated = datetime.now().strftime("%d %b %Y, %I:%M %p")
    st.session_state.last_city = city_name
    st.session_state.weather_history = None
    st.session_state.alert_history = None
    return True


def fmt(value, decimals=1, suffix=""):
    try:
        return f"{float(value):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"
