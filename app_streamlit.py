"""Professional API-connected Streamlit dashboard.
Run: .\\.venv\\Scripts\\python.exe -m streamlit run app_streamlit_api.py
"""
from datetime import datetime
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
        st.error("Could not connect to FastAPI. Start the backend in a separate terminal and try again.")
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


def empty(message):
    st.markdown(f'<div class="empty-state">{message}</div>', unsafe_allow_html=True)


# Sidebar controls
with st.sidebar:
    st.markdown("## 🌦️ WeatherPulse")
    st.caption("WEATHER INTELLIGENCE PLATFORM")
    st.divider()
    st.markdown("### Dashboard settings")
    api_url = st.text_input("FastAPI base URL", "http://127.0.0.1:8000").strip().rstrip("/")
    city = st.text_input("City", "Pune").strip()
    provider = st.selectbox("Weather provider", ["open-meteo", "openweathermap"], format_func=lambda x: "Open-Meteo" if x == "open-meteo" else "OpenWeatherMap")
    refresh = st.button("↻  Refresh weather", type="primary", use_container_width=True)
    st.divider()
    st.markdown("### Backend connection")
    if st.button("Check API health", use_container_width=True):
        health = api_get(api_url, "/health")
        if health:
            st.success(f"API status: {health.get('status', 'Unknown')}")
            st.caption(f"Database: {health.get('database', 'Unknown')}")
    st.divider()
    st.caption("Open-Meteo works without an API key.")

if refresh:
    if not city:
        st.sidebar.error("Enter a city name first.")
    elif load_weather(api_url, city, provider):
       st.toast(f"Weather updated for {city}", icon="✅")

shown_city = st.session_state.last_city or city or "Select a city"
st.markdown(f'''<div class="hero"><div class="hero-kicker">Weather intelligence · Live overview</div><div class="hero-title">Weather dashboard</div><div class="hero-subtitle">Monitor current conditions, forecast trends and weather alerts for <strong>{shown_city}</strong>.</div></div>''', unsafe_allow_html=True)
if st.session_state.last_updated:
    st.markdown(f'<span class="status-pill">● Data loaded</span> &nbsp; <span class="muted">Last updated: {st.session_state.last_updated}</span>', unsafe_allow_html=True)
else:
    st.caption("No weather data loaded yet. Choose a city and select Refresh weather in the sidebar.")

# Current conditions
st.markdown('<div class="section-heading">Current conditions</div><div class="section-subtitle">Latest available weather observations for the selected city.</div>', unsafe_allow_html=True)
current_data = st.session_state.weather_data
if current_data:
    current = current_data.get("current", {}) or {}
    location = current_data.get("city", shown_city)
    country = current_data.get("country", "")
    st.markdown(f"**{location}{', ' + country if country else ''}** · Source: `{current_data.get('source', 'N/A')}`")
    cols = st.columns(4)
    for col, (label, value, help_text) in zip(cols, [
        ("Temperature", fmt(current.get("temp_c"), 1, " °C"), "Air temperature"),
        ("Feels like", fmt(current.get("feels_c"), 1, " °C"), "Perceived temperature"),
        ("Humidity", fmt(current.get("humidity_pct"), 0, "%"), "Relative humidity"),
        ("Wind speed", fmt(current.get("wind_ms"), 1, " m/s"), "Current wind"),
    ]):
        col.metric(label, value, help=help_text)
    cols = st.columns(3)
    for col, (label, value) in zip(cols, [
        ("Wind gust", fmt(current.get("gust_ms"), 1, " m/s")),
        ("Precipitation", fmt(current.get("precip_mm"), 1, " mm")),
        ("Conditions", str(current.get("condition", "N/A"))),
    ]):
        col.metric(label, value)
    if current.get("time"):
        st.caption(f"Observation time: {current.get('time')}")
    for note in current_data.get("notes", []) or []:
        st.info(note)
else:
    empty("Your current weather overview will appear here after you load weather data.")

st.divider()
t_overview, t_forecast, t_alerts, t_history = st.tabs(["Overview", "Forecast", "Alerts", "History"])

with t_overview:
    st.markdown('<div class="section-heading">Weather snapshot</div><div class="section-subtitle">A quick view of forecast availability and active alerts.</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    forecast_data = st.session_state.forecast_data
    alert_data = st.session_state.alert_data
    with left:
        st.markdown("**Forecast availability**")
        if forecast_data is not None:
            rows = forecast_data.get("forecast", []) or []
            st.metric("Forecast records", len(rows))
            st.caption("Explore trends in the Forecast tab.")
        else:
            empty("Load weather data to view forecast information.")
    with right:
        st.markdown("**Active weather alerts**")
        if alert_data is not None:
            alerts = alert_data.get("alerts", []) or []
            st.metric("Alert count", alert_data.get("count", len(alerts)))
            if not alerts:
                st.success("No active alerts returned by the backend.")
            else:
                st.warning("Active alerts detected. Review the Alerts tab.")
        else:
            empty("Load weather data to check active alerts.")

with t_forecast:
    st.markdown(
        '<div class="section-heading">Forecast analytics</div>'
        '<div class="section-subtitle">Explore temperature, precipitation probability and wind trends.</div>',
        unsafe_allow_html=True,
    )

    forecast_data = st.session_state.forecast_data
    rows = forecast_data.get("forecast", []) if forecast_data else []
    df = pd.DataFrame(rows)

    if not df.empty:
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
            df = df.dropna(subset=["time"]).sort_values("time")

        if df.empty:
            empty("Forecast records were returned, but no valid timestamps were found.")
        else:
            left, right = st.columns(2)

            with left:
                st.markdown("**Temperature trend**")
                if "temp_c" in df.columns:
                    chart = (
                        df.set_index("time")[["temp_c"]]
                        .apply(pd.to_numeric, errors="coerce")
                        .dropna()
                    )
                    if not chart.empty:
                        st.line_chart(chart, use_container_width=True)
                    else:
                        empty("Temperature values are unavailable.")
                else:
                    empty("Temperature forecast is unavailable.")

            with right:
                st.markdown("**Rain probability**")
                if "precip_prob_pct" in df.columns:
                    chart = (
                        df.set_index("time")[["precip_prob_pct"]]
                        .apply(pd.to_numeric, errors="coerce")
                        .dropna()
                    )
                    if not chart.empty:
                        st.area_chart(chart, use_container_width=True)
                    else:
                        empty("Rain probability values are unavailable.")
                else:
                    empty("Rain probability is unavailable in this response.")

            st.markdown("**Wind speed and gusts**")
            wind_cols = [column for column in ("wind_ms", "gust_ms") if column in df.columns]

            if wind_cols:
                chart = (
                    df.set_index("time")[wind_cols]
                    .apply(pd.to_numeric, errors="coerce")
                    .dropna(how="all")
                )
                if not chart.empty:
                    st.line_chart(chart, use_container_width=True)
                else:
                    empty("Wind values are unavailable.")
            else:
                empty("Wind forecast values are unavailable.")

            with st.expander("View detailed forecast records"):
                st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty("No forecast data is loaded. Select Refresh weather in the sidebar.")


with t_alerts:
    st.markdown('<div class="section-heading">Weather alert centre</div><div class="section-subtitle">Alerts generated by the application backend rules.</div>', unsafe_allow_html=True)
    alert_data = st.session_state.alert_data
    if alert_data is not None:
        alerts = alert_data.get("alerts", []) or []
        cols = st.columns(3)
        cols[0].metric("Active alerts", alert_data.get("count", len(alerts)))
        cols[1].metric("City", alert_data.get("city", shown_city))
        cols[2].metric("Source", alert_data.get("source", "N/A"))
        if not alerts:
            st.success("No active weather alerts. The backend did not detect any alert conditions.")
        else:
            for index, alert in enumerate(alerts, 1):
                severity = str(alert.get("severity", "info")).lower()
                message = f"**{alert.get('title', f'Weather alert {index}')}**\n\n{alert.get('message', 'No additional details provided.')}"
                if severity in ("critical", "danger"):
                    st.error(message)
                elif severity in ("warning", "high"):
                    st.warning(message)
                else:
                    st.info(message)
    else:
        empty("Active alerts will appear here after you load weather data.")

with t_history:
    st.markdown('<div class="section-heading">Historical records</div><div class="section-subtitle">Review saved weather observations and previously recorded alerts.</div>', unsafe_allow_html=True)
    history_city = st.session_state.last_city or city
    left, right = st.columns(2)
    with left:
        if st.button("Load weather history", use_container_width=True):
            result = api_get(api_url, "/weather/history", {"city": history_city, "limit": 100})
            if result is not None:
                st.session_state.weather_history = result
    with right:
        if st.button("Load alert history", use_container_width=True):
            result = api_get(api_url, "/alerts/history", {"city": history_city, "limit": 100})
            if result is not None:
                st.session_state.alert_history = result
    st.markdown("**Weather history**")
    history = st.session_state.weather_history
    if history is not None:
        if history:
            records = []
            for item in history:
                obs = item.get("current", {}) or {}
                records.append({"Observed at": item.get("observed_at"), "City": item.get("city"), "Temperature (°C)": obs.get("temp_c"), "Feels like (°C)": obs.get("feels_c"), "Humidity (%)": obs.get("humidity_pct"), "Wind (m/s)": obs.get("wind_ms"), "Condition": obs.get("condition")})
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
        else:
            st.caption("No historical weather records were found for this city.")
    else:
        st.caption("Select Load weather history to retrieve saved observations.")
    st.divider()
    st.markdown("**Alert history**")
    history = st.session_state.alert_history
    if history is not None:
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        else:
            st.caption("No historical alert records were found for this city.")
    else:
        st.caption("Select Load alert history to retrieve saved alerts.")

st.divider()
a, b = st.columns(2)
a.caption("WEATHERPULSE · Weather Forecast & Alert Application")
b.caption("Streamlit · FastAPI · SQLite")
