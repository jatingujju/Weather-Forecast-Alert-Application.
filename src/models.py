"""
models.py - the common data format used by the WHOLE project.

Every weather source (simulation, Open-Meteo, OpenWeatherMap) is converted
into a WeatherBundle with the same hourly columns and the same units:
    temperature in deg C, wind in m/s, rain in mm, humidity in %.
After that, the alert rules never need to know where the data came from.
"""
from dataclasses import dataclass, field

import pandas as pd

HOURLY_COLUMNS = [
    "time",             # local time of the forecast step
    "temp_c",
    "feels_c",          # "feels like" temperature
    "humidity_pct",
    "wind_ms",
    "gust_ms",
    "precip_mm",        # rain in this step (1 h or 3 h)
    "precip_prob_pct",  # chance of rain
    "uv_index",         # may be NaN if the source does not give it
    "condition",        # text such as "Light rain"
    "is_thunder",       # True if a thunderstorm is forecast
    "step_hours",       # length of this forecast step (1 or 3)
]


@dataclass
class WeatherBundle:
    """Weather for one city."""
    city: str
    country: str
    lat: float
    lon: float
    source: str                  # "simulation", "open-meteo" or "openweathermap"
    now: pd.Timestamp            # "current time" in the city (local time)
    current: dict                # current conditions
    hourly: pd.DataFrame         # forecast table with HOURLY_COLUMNS
    notes: list = field(default_factory=list)   # e.g. "UV not provided"
