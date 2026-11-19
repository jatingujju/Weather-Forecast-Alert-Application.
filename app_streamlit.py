"""
app_streamlit.py - OPTIONAL interactive dashboard.

Run with:   streamlit run app_streamlit.py
(needs:     pip install streamlit)
"""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src import alerts as alert_engine
from src import analysis, config, providers, simulator, visualize

config.load_env()
st.set_page_config(page_title="Weather Forecast & Alerts", layout="wide")
st.title("Weather Forecast & Alert Application")

# ---------- Sidebar: where does the data come from? ----------
mode = st.sidebar.radio("Data source", ["Simulation (no internet)", "Live weather (Open-Meteo)",
                                        "Live weather (OpenWeatherMap)"])
th = config.Thresholds()
th.heat_warn_c = st.sidebar.slider("Heat warning (C)", 25, 45, int(th.heat_warn_c))
th.rain_prob_warn_pct = st.sidebar.slider("Rain chance warning (%)", 10, 100, int(th.rain_prob_warn_pct))
th.gust_warn_ms = st.sidebar.slider("Wind gust warning (m/s)", 5, 30, int(th.gust_warn_ms))

if mode.startswith("Simulation"):
    names = list(pd.read_csv(config.SAMPLE_CITIES_CSV)["city"])
    chosen = st.sidebar.multiselect("Cities", names, default=names)
else:
    text = st.sidebar.text_input("City (use commas to add more, e.g. Pune, Mumbai)", "Pune")
    chosen = [c.strip() for c in text.split(",") if c.strip()]
    st.sidebar.caption("The OpenWeatherMap key is read from your .env file (never typed here).")

if not chosen:
    st.warning("Choose or type at least one city.")
    st.stop()

# ---------- Load weather when the button is pressed ----------
if st.sidebar.button("Get weather") or "bundles" not in st.session_state:
    try:
        if mode.startswith("Simulation"):
            bundles = simulator.load_sample_bundles(chosen)
        elif "OpenWeatherMap" in mode:
            key = config.get_setting("OPENWEATHER_API_KEY")
            bundles = [providers.fetch_openweathermap(c, key) for c in chosen]
        else:
            bundles = [providers.fetch_open_meteo(c, config.FORECAST_DAYS) for c in chosen]
        st.session_state["bundles"] = bundles
    except (providers.WeatherError, ValueError) as error:
        st.error(str(error))
        st.stop()

bundles = st.session_state["bundles"]
alerts = alert_engine.evaluate_all(bundles, th)
st.caption("Simulation data is fake and for learning only." if bundles[0].source == "simulation"
           else f"Live data from {bundles[0].source}.")

# ---------- Alerts ----------
st.subheader("Alerts")
if not alerts:
    st.success("No alerts - conditions look calm.")
for a in alerts:
    text = f"**{a.city} - {a.title}.** {a.message}"
    {"critical": st.error, "warning": st.warning, "info": st.info}[a.severity](text)

# ---------- Current weather ----------
st.subheader("Current weather")
st.dataframe(analysis.current_table(bundles))

# ---------- Charts ----------
if len(bundles) > 1:
    for plot in (visualize.plot_temperature_comparison, visualize.plot_rain_comparison):
        fig = plot(bundles, th)
        st.pyplot(fig)
        plt.close(fig)
    fig = visualize.plot_alert_matrix(alerts, [b.city for b in bundles])
    st.pyplot(fig)
    plt.close(fig)

city = st.selectbox("City details", [b.city for b in bundles])
chosen_bundle = next(b for b in bundles if b.city == city)
fig = visualize.plot_city_dashboard(chosen_bundle, th)
st.pyplot(fig)
plt.close(fig)
st.subheader("Daily outlook")
st.dataframe(analysis.daily_summary(chosen_bundle))
