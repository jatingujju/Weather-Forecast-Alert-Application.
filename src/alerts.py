"""
alerts.py - the alert rules.

Each rule looks at a TIME WINDOW of the forecast (for example "the next 12
hours") and returns an Alert or None. Windows are based on real timestamps,
so the rules work for 1-hour and 3-hour forecast steps alike.
"""
from dataclasses import asdict, dataclass

import pandas as pd

from src.config import Thresholds

SEVERITY_RANK = {"info": 1, "warning": 2, "critical": 3}
CATEGORIES = ["Heat", "Rain", "Wind", "Thunderstorm", "Humidity", "UV"]


@dataclass
class Alert:
    city: str
    category: str      # one of CATEGORIES
    severity: str      # info | warning | critical
    title: str
    message: str
    time: object = None   # when the problem peaks / starts

    def to_dict(self):
        d = asdict(self)
        d["time"] = "" if self.time is None else f"{self.time:%Y-%m-%d %H:%M}"
        return d


def window(hourly, start, hours):
    """Forecast rows from `start` up to (but not including) start + hours."""
    mask = (hourly["time"] >= start) & (hourly["time"] < start + pd.Timedelta(hours=hours))
    return hourly[mask]


def _when(t):
    return f"{t:%d %b %H:%M}"


def check_heat(city, now, hourly, th):
    w = window(hourly, now, 48)
    if w.empty or w["temp_c"].isna().all():
        return None
    row = w.loc[w["temp_c"].idxmax()]
    t = row["temp_c"]
    if t >= th.heat_critical_c:
        severity, title = "critical", "Extreme heat"
    elif t >= th.heat_warn_c:
        severity, title = "warning", "High temperature"
    else:
        return None
    return Alert(city, "Heat", severity, title,
                 f"Temperature expected to reach {t:.1f}C around {_when(row['time'])} "
                 f"(limit {th.heat_warn_c:.0f}C / {th.heat_critical_c:.0f}C). "
                 f"Avoid outdoor work at midday and drink plenty of water.", row["time"])


def check_rain(city, now, hourly, th):
    w12, w24 = window(hourly, now, 12), window(hourly, now, 24)
    if w12.empty:
        return None
    max_prob = w12["precip_prob_pct"].max()
    total = w24["precip_mm"].sum()
    wet = w24[w24["precip_mm"] > 0.5]
    start = wet["time"].iloc[0] if not wet.empty else None
    if total >= th.heavy_rain_24h_mm:
        return Alert(city, "Rain", "critical", "Heavy rain",
                     f"About {total:.0f} mm of rain expected in the next 24 h "
                     f"(limit {th.heavy_rain_24h_mm:.0f} mm), starting around "
                     f"{_when(start) if start is not None else 'soon'}. Risk of waterlogging.", start)
    if max_prob >= th.rain_prob_warn_pct:
        peak = w12.loc[w12["precip_prob_pct"].idxmax()]
        return Alert(city, "Rain", "warning", "Rain likely",
                     f"Up to {max_prob:.0f}% chance of rain in the next 12 h "
                     f"(limit {th.rain_prob_warn_pct:.0f}%); about {total:.0f} mm in 24 h. "
                     f"Carry an umbrella.", peak["time"])
    return None


def check_wind(city, now, hourly, th):
    w = window(hourly, now, 24)
    if w.empty or w["gust_ms"].isna().all():
        return None
    row = w.loc[w["gust_ms"].idxmax()]
    g = row["gust_ms"]
    if g >= th.gust_critical_ms:
        severity, title = "critical", "Very strong wind gusts"
    elif g >= th.gust_warn_ms:
        severity, title = "warning", "Strong wind gusts"
    else:
        return None
    return Alert(city, "Wind", severity, title,
                 f"Gusts up to {g:.1f} m/s ({g * 3.6:.0f} km/h) around {_when(row['time'])} "
                 f"(limit {th.gust_warn_ms:.0f} / {th.gust_critical_ms:.0f} m/s). "
                 f"Secure loose objects; avoid travel on exposed roads.", row["time"])


def check_thunder(city, now, hourly, th):
    w = window(hourly, now, 24)
    storm = w[w["is_thunder"]]
    if storm.empty:
        return None
    hours = float(storm["step_hours"].sum())
    severity = "critical" if hours >= th.thunder_critical_hours else "warning"
    first = storm["time"].iloc[0]
    return Alert(city, "Thunderstorm", severity, "Thunderstorm expected",
                 f"About {hours:.0f} h of thunderstorm in the next 24 h, starting around "
                 f"{_when(first)}. Stay indoors and avoid open areas.", first)


def check_humidity(city, now, hourly, th):
    w = window(hourly, now, 12)
    if w.empty or w["humidity_pct"].isna().all():
        return None
    avg = w["humidity_pct"].mean()
    if avg < th.humidity_warn_pct:
        return None
    return Alert(city, "Humidity", "info", "Very humid",
                 f"Average humidity {avg:.0f}% over the next 12 h "
                 f"(limit {th.humidity_warn_pct:.0f}%). It will feel muggy.", now)


def check_uv(city, now, hourly, th):
    # rest of TODAY only, so an old peak never raises a stale alert
    w = hourly[(hourly["time"].dt.date == now.date()) & (hourly["time"] >= now)]
    if w.empty or w["uv_index"].isna().all():
        return None
    row = w.loc[w["uv_index"].idxmax()]
    uv = row["uv_index"]
    if uv >= th.uv_critical:
        severity, title = "critical", "Extreme UV"
    elif uv >= th.uv_warn:
        severity, title = "warning", "High UV"
    else:
        return None
    return Alert(city, "UV", severity, title,
                 f"UV index up to {uv:.1f} around {_when(row['time'])} "
                 f"(limit {th.uv_warn:.0f} / {th.uv_critical:.0f}). Use sunscreen and cover up.", row["time"])


RULES = [check_heat, check_rain, check_wind, check_thunder, check_humidity, check_uv]


def evaluate(bundle, thresholds=None):
    """Run every rule on one city. Returns alerts, most severe first."""
    th = thresholds or Thresholds()
    found = []
    for rule in RULES:
        alert = rule(bundle.city, bundle.now, bundle.hourly, th)
        if alert is not None:
            found.append(alert)
    found.sort(key=lambda a: (-SEVERITY_RANK[a.severity], a.category))
    return found


def evaluate_all(bundles, thresholds=None):
    """Run the rules for several cities."""
    alerts = []
    for b in bundles:
        alerts.extend(evaluate(b, thresholds))
    return alerts
