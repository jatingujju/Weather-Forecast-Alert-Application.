"""Adapter from the existing weather providers to API-ready dictionaries."""
import math
import pandas as pd
from src import config, providers


def fetch_bundle(city: str, provider: str = "open-meteo"):
    city = city.strip()
    if not city:
        raise ValueError("City must not be empty.")
    if provider == "open-meteo":
        return providers.fetch_open_meteo(city, config.FORECAST_DAYS)
    if provider == "openweathermap":
        config.load_env()
        return providers.fetch_openweathermap(city, config.get_setting("OPENWEATHER_API_KEY"))
    raise ValueError("Unsupported provider. Choose open-meteo or openweathermap.")


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def bundle_current(bundle):
    return json_safe(bundle.current)


def bundle_forecast(bundle):
    return json_safe(bundle.hourly.to_dict(orient="records"))
