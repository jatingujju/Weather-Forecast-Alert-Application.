"""
providers.py - gets REAL weather from the internet and converts it into the
common WeatherBundle format (see models.py).

Two providers:
  * Open-Meteo      - free, NO API key needed (default live mode)
  * OpenWeatherMap  - free tier, needs an API key stored in .env

Every problem (no internet, wrong key, unknown city ...) becomes a
WeatherError with a friendly message. API keys are never printed.
"""
import time
from datetime import timedelta

import numpy as np
import pandas as pd
import requests

from src.models import HOURLY_COLUMNS, WeatherBundle


class WeatherError(Exception):
    """A problem getting or reading weather data (message is user-friendly)."""


def _get_json(url, params, retries=2, timeout=15, sleep=time.sleep):
    """GET a URL and return its JSON. Retries on network trouble / server errors."""
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retries:
                sleep(1.0 * (attempt + 1))
                continue
            # NOTE: the original error text can contain the URL (and API key),
            # so we show our own message instead.
            raise WeatherError("Could not reach the weather service. "
                               "Check your internet connection and try again.")

        code = response.status_code
        if code >= 500 and attempt < retries:
            sleep(1.0 * (attempt + 1))
            continue
        if code == 401:
            raise WeatherError("The API key was rejected (HTTP 401). Check OPENWEATHER_API_KEY "
                               "in your .env file. New keys can take a while to activate.")
        if code == 404:
            raise WeatherError("City not found (HTTP 404). Check the spelling, or try "
                               "'City,CountryCode' such as 'Pune,IN'.")
        if code == 429:
            raise WeatherError("Too many requests (HTTP 429). Wait a minute and try again.")
        if code >= 500:
            raise WeatherError(f"The weather service is having problems (HTTP {code}). Try again later.")
        if code != 200:
            raise WeatherError(f"Unexpected response from the weather service (HTTP {code}).")
        try:
            return response.json()
        except ValueError:
            raise WeatherError("The weather service returned data that is not valid JSON.")


# ======================================================================
# Open-Meteo (no key)
# ======================================================================
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes used by Open-Meteo
WMO_TEXT = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}
THUNDER_CODES = (95, 96, 99)


def geocode_open_meteo(city):
    """Turn a city name into latitude/longitude."""
    name = city.split(",")[0].strip()      # "Pune,IN" -> "Pune"
    payload = _get_json(GEOCODE_URL, {"name": name, "count": 1, "language": "en", "format": "json"})
    results = payload.get("results")
    if not results:
        raise WeatherError(f"City not found: '{city}'. Check the spelling.")
    r = results[0]
    return {"name": r.get("name", name), "country": r.get("country_code", ""),
            "lat": r["latitude"], "lon": r["longitude"]}


def parse_open_meteo(payload, name, country, lat, lon):
    """Convert an Open-Meteo JSON response into a WeatherBundle."""
    h = payload.get("hourly")
    if not h or "time" not in h:
        raise WeatherError("Open-Meteo returned an unexpected format (no hourly data).")

    def column(key):
        # missing or null values become NaN instead of crashing
        values = h.get(key, [None] * len(h["time"]))
        return pd.to_numeric(pd.Series(values), errors="coerce")

    code = column("weather_code")
    wind = column("wind_speed_10m")
    hourly = pd.DataFrame({
        "time": pd.to_datetime(h["time"]),
        "temp_c": column("temperature_2m"),
        "feels_c": column("apparent_temperature"),
        "humidity_pct": column("relative_humidity_2m"),
        "wind_ms": wind,
        "gust_ms": column("wind_gusts_10m").fillna(wind),
        "precip_mm": column("precipitation").fillna(0),
        "precip_prob_pct": column("precipitation_probability").fillna(0),
        "uv_index": column("uv_index"),
        "condition": code.map(WMO_TEXT).fillna("Unknown"),
        "is_thunder": code.isin(THUNDER_CODES),
        "step_hours": 1,
    })[HOURLY_COLUMNS]
    # QA: times must increase and have no duplicates
    hourly = hourly.sort_values("time").drop_duplicates("time").reset_index(drop=True)

    c = payload.get("current") or {}
    now = pd.to_datetime(c["time"]) if c.get("time") else hourly["time"].iloc[0]
    cur_code = c.get("weather_code")
    current = {
        "time": now,
        "temp_c": c.get("temperature_2m"),
        "feels_c": c.get("apparent_temperature"),
        "humidity_pct": c.get("relative_humidity_2m"),
        "wind_ms": c.get("wind_speed_10m"),
        "gust_ms": c.get("wind_gusts_10m"),
        "precip_mm": c.get("precipitation", 0),
        "condition": WMO_TEXT.get(cur_code, "Unknown"),
    }
    return WeatherBundle(city=name, country=country, lat=lat, lon=lon, source="open-meteo",
                         now=now, current=current, hourly=hourly,
                         notes=["Live data from Open-Meteo (no API key needed)."])


def fetch_open_meteo(city, days=5):
    """Find the city, download its forecast and return a WeatherBundle."""
    place = geocode_open_meteo(city)
    params = {
        "latitude": place["lat"], "longitude": place["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
                   "weather_code,wind_speed_10m,wind_gusts_10m",
        "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                  "precipitation_probability,precipitation,weather_code,"
                  "wind_speed_10m,wind_gusts_10m,uv_index",
        "wind_speed_unit": "ms",      # metres per second
        "timezone": "auto",           # times are in the city's own timezone
        "forecast_days": days,
    }
    payload = _get_json(FORECAST_URL, params)
    return parse_open_meteo(payload, place["name"], place["country"], place["lat"], place["lon"])


# ======================================================================
# OpenWeatherMap (needs API key)
# ======================================================================
OWM_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def parse_openweathermap(current, forecast):
    """Convert OpenWeatherMap 'current' + '5 day / 3 hour' JSON into a WeatherBundle."""
    items = forecast.get("list")
    if not items:
        raise WeatherError("OpenWeatherMap returned no forecast data.")
    place = forecast.get("city", {})
    shift = timedelta(seconds=place.get("timezone", 0))   # UTC -> city's local time

    rows = []
    for item in items:
        w = (item.get("weather") or [{}])[0]
        main, wind = item.get("main", {}), item.get("wind", {})
        rain = (item.get("rain") or {}).get("3h", 0) + (item.get("snow") or {}).get("3h", 0)
        rows.append({
            "time": pd.to_datetime(item["dt"], unit="s") + shift,
            "temp_c": main.get("temp"),
            "feels_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "wind_ms": wind.get("speed"),
            "gust_ms": wind.get("gust", wind.get("speed")),
            "precip_mm": rain,
            "precip_prob_pct": item.get("pop", 0) * 100,
            "uv_index": np.nan,              # not in the free forecast
            "condition": str(w.get("description", "unknown")).capitalize(),
            "is_thunder": 200 <= w.get("id", 0) < 300,
            "step_hours": 3,
        })
    hourly = pd.DataFrame(rows)[HOURLY_COLUMNS]
    hourly = hourly.sort_values("time").drop_duplicates("time").reset_index(drop=True)

    cw = (current.get("weather") or [{}])[0]
    cmain, cwind = current.get("main", {}), current.get("wind", {})
    cshift = timedelta(seconds=current.get("timezone", place.get("timezone", 0)))
    now = pd.to_datetime(current["dt"], unit="s") + cshift if "dt" in current else hourly["time"].iloc[0]
    cur = {
        "time": now,
        "temp_c": cmain.get("temp"),
        "feels_c": cmain.get("feels_like"),
        "humidity_pct": cmain.get("humidity"),
        "wind_ms": cwind.get("speed"),
        "gust_ms": cwind.get("gust", cwind.get("speed")),
        "precip_mm": (current.get("rain") or {}).get("1h", 0),
        "condition": str(cw.get("description", "unknown")).capitalize(),
    }
    coord = place.get("coord", {})
    return WeatherBundle(
        city=place.get("name") or current.get("name", "Unknown"),
        country=place.get("country", ""), lat=coord.get("lat", 0.0), lon=coord.get("lon", 0.0),
        source="openweathermap", now=now, current=cur, hourly=hourly,
        notes=["Live data from OpenWeatherMap (3-hour steps).",
               "UV index is not provided by the free OpenWeatherMap forecast, so no UV alert."])


def fetch_openweathermap(city, api_key):
    """Download current weather + forecast for a city and return a WeatherBundle."""
    if not api_key:
        raise WeatherError("No API key found. Put OPENWEATHER_API_KEY=... in your .env file "
                           "(copy .env.example to .env first).")
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = _get_json(OWM_CURRENT_URL, params)
    forecast = _get_json(OWM_FORECAST_URL, params)
    return parse_openweathermap(current, forecast)
