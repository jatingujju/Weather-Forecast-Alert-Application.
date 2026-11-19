"""
analysis.py - turns forecast tables into summaries (no printing, no plotting).
"""
import pandas as pd

from src.alerts import CATEGORIES, SEVERITY_RANK, window


def current_table(bundles):
    """One row per city with the current conditions."""
    rows = []
    for b in bundles:
        c = b.current
        rows.append({"city": b.city, "source": b.source, "time": c["time"],
                     "temp_c": c["temp_c"], "feels_c": c["feels_c"],
                     "humidity_pct": c["humidity_pct"], "wind_ms": c["wind_ms"],
                     "condition": c["condition"]})
    return pd.DataFrame(rows)


def daily_summary(bundle):
    """Daily min/max temperature, rain, wind, humidity and UV from the hourly data."""
    h = bundle.hourly.copy()
    h["date"] = h["time"].dt.strftime("%Y-%m-%d")
    out = h.groupby("date").agg(
        temp_max_c=("temp_c", "max"),
        temp_min_c=("temp_c", "min"),
        rain_mm=("precip_mm", "sum"),
        rain_chance_max_pct=("precip_prob_pct", "max"),
        gust_max_ms=("gust_ms", "max"),
        humidity_avg_pct=("humidity_pct", "mean"),
        uv_max=("uv_index", "max"),
    ).round(1).reset_index()
    out.insert(0, "city", bundle.city)
    return out


def forecast_summary(bundle, hours=48):
    """Key facts about the next `hours` hours (used in the text report)."""
    w = window(bundle.hourly, bundle.now, hours)
    if w.empty:
        return {}
    hot, cold = w.loc[w["temp_c"].idxmax()], w.loc[w["temp_c"].idxmin()]
    wet = w[w["precip_mm"] > 0.5]
    return {
        "hours": hours,
        "hottest_c": hot["temp_c"], "hottest_time": hot["time"],
        "coolest_c": cold["temp_c"], "coolest_time": cold["time"],
        "rain_total_mm": w["precip_mm"].sum(),
        "rain_start": wet["time"].iloc[0] if not wet.empty else None,
        "max_rain_chance_pct": w["precip_prob_pct"].max(),
        "max_gust_ms": w["gust_ms"].max(),
        "thunder_hours": float(w.loc[w["is_thunder"], "step_hours"].sum()),
    }


def all_hourly(bundles):
    """All cities' hourly forecasts stacked into one table."""
    parts = []
    for b in bundles:
        part = b.hourly.copy()
        part.insert(0, "city", b.city)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def alert_matrix(alerts, cities):
    """City x alert-type table with severity 0 (none) to 3 (critical)."""
    m = pd.DataFrame(0, index=cities, columns=CATEGORIES)
    for a in alerts:
        m.loc[a.city, a.category] = max(m.loc[a.city, a.category], SEVERITY_RANK[a.severity])
    return m
