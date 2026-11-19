"""
config.py - settings in one place: folders, alert thresholds, .env loading.

The API key is NEVER written in code. It lives in a file called .env
(which .gitignore keeps off GitHub). See .env.example.
"""
import os
from dataclasses import dataclass
from pathlib import Path

# ---------- Folders ----------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
IMAGE_DIR = BASE_DIR / "images"
REPORT_DIR = BASE_DIR / "reports"
SAMPLE_CITIES_CSV = DATA_DIR / "sample_cities.csv"

# ---------- Simulation clock ----------
# Simulation mode pretends it is this moment, so every run gives the SAME
# results (good for screenshots, tests and your README).
SIM_NOW = "2026-11-18 09:00"
SIM_HOURS = 120          # 5 days of hourly data
SIM_SEED = 42

# ---------- Forecast window ----------
FORECAST_DAYS = 5


@dataclass
class Thresholds:
    """Alert limits. Change them here or with command-line options."""
    heat_warn_c: float = 37.0          # temperature in the next 48 h
    heat_critical_c: float = 40.0
    rain_prob_warn_pct: float = 60.0   # rain chance in the next 12 h
    heavy_rain_24h_mm: float = 50.0    # total rain in the next 24 h
    gust_warn_ms: float = 15.0         # wind gusts in the next 24 h (15 m/s = 54 km/h)
    gust_critical_ms: float = 20.0     # 20 m/s = 72 km/h
    humidity_warn_pct: float = 85.0    # average humidity in the next 12 h
    uv_warn: float = 8.0               # UV index today
    uv_critical: float = 11.0
    thunder_critical_hours: int = 3    # hours of thunderstorm that make it critical


def load_env(path=None):
    """
    Read KEY=VALUE lines from a .env file into os.environ.
    Existing environment variables are not overwritten. Returns the keys loaded.
    (A tiny reader, so no extra library is needed.)
    """
    path = Path(path) if path else BASE_DIR / ".env"
    loaded = []
    if not path.exists():
        return loaded
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def get_setting(name, default=None):
    """Read a setting from the environment (after load_env)."""
    return os.environ.get(name, default)
