"""
simulator.py - makes realistic but FAKE weather, so the whole project works
without internet or an API key.

Each city follows a "scenario" (a hand-designed weather story). They are
ILLUSTRATIVE - they are not real forecasts for those cities.
"""
import numpy as np
import pandas as pd

from src import config
from src.models import HOURLY_COLUMNS, WeatherBundle

# rain event  = (start_hour, duration_hours, mm_per_hour, peak_chance_pct)
# gust event  = (start_hour, duration_hours, extra_m_per_s)
# thunder     = (start_hour, duration_hours)
# Hours are counted from midnight of day 0 (the simulation starts 09:00).
SCENARIOS = {
    "monsoon_downpour": dict(t_mean=28.0, t_amp=2.5, offsets=[0, -0.5, 0, 0.5, 0],
                             hum=90, wind=5.0, uv_peak=6.0, base_prob=25,
                             rain=[(13, 7, 8.5, 95), (37, 6, 4.0, 85)],
                             thunder=[], gusts=[(14, 5, 9.0)]),
    "heat_wave": dict(t_mean=33.0, t_amp=8.0, offsets=[0, 2, 0.5, -1, -2],
                      hum=25, wind=3.0, uv_peak=10.0, base_prob=3,
                      rain=[], thunder=[], gusts=[]),
    "cyclone_storm": dict(t_mean=28.0, t_amp=2.0, offsets=[0, -1, -1, 0, 0],
                          hum=92, wind=9.0, uv_peak=4.0, base_prob=40,
                          rain=[(15, 10, 8.0, 98)], thunder=[(16, 6)],
                          gusts=[(16, 7, 14.0)]),
    "mild_clear": dict(t_mean=24.0, t_amp=4.0, offsets=[0, 0.5, 0, 0, -0.5],
                       hum=62, wind=3.0, uv_peak=7.5, base_prob=8,
                       rain=[(58, 2, 0.6, 45)], thunder=[], gusts=[]),
    "humid_thunder": dict(t_mean=31.0, t_amp=3.0, offsets=[0, 0, 0.5, 0, 0],
                          hum=90, wind=4.0, uv_peak=8.0, base_prob=30,
                          rain=[(17, 3, 6.0, 90)], thunder=[(17, 2)],
                          gusts=[(17, 2, 6.0)]),
    "hot_high_uv": dict(t_mean=32.0, t_amp=6.0, offsets=[0, 0, 0, 0, 0],
                        hum=30, wind=3.5, uv_peak=11.5, base_prob=3,
                        rain=[], thunder=[], gusts=[]),
}


def _describe(temp, rain_mm, thunder, humidity):
    """Turn numbers into a short weather description."""
    if thunder:
        return "Thunderstorm"
    if rain_mm >= 2.5:
        return "Heavy rain"
    if rain_mm >= 0.1:
        return "Light rain"
    if temp >= 38:
        return "Hot and sunny"
    if humidity >= 85:
        return "Overcast and humid"
    return "Clear to partly cloudy"


def simulate_city(city, country, lat, lon, scenario, seed=0):
    """Create a WeatherBundle with 5 days of hourly data for one city."""
    spec = SCENARIOS[scenario]
    rng = np.random.default_rng(config.SIM_SEED + seed)

    start = pd.Timestamp(config.SIM_NOW).normalize()
    n = config.SIM_HOURS
    times = pd.date_range(start, periods=n, freq="h")
    hour_idx = np.arange(n)
    hod = hour_idx % 24
    day = hour_idx // 24

    # --- rain, chance of rain, thunder, gusts from the scenario events ---
    precip = np.zeros(n)
    prob = np.full(n, float(spec["base_prob"]))
    thunder = np.zeros(n, dtype=bool)
    gust_bump = np.zeros(n)

    for s, dur, mm, peak in spec["rain"]:
        for k in range(dur):                      # bell-shaped rain intensity
            if s + k < n:
                precip[s + k] += mm * np.sin(np.pi * (k + 0.5) / dur) * (np.pi / 2)
        for j in range(6):                        # chance rises in the 6 h before
            i = s - 6 + j
            if 0 <= i < n:
                prob[i] = max(prob[i], spec["base_prob"] + (peak - spec["base_prob"]) * (j + 1) / 7)
        for k in range(dur):                      # chance stays high during rain
            if s + k < n:
                prob[s + k] = max(prob[s + k], peak)
        for j in range(3):                        # and falls slowly after it
            i = s + dur + j
            if i < n:
                prob[i] = max(prob[i], peak - (peak - spec["base_prob"]) * (j + 1) / 4)
    for s, dur in spec["thunder"]:
        thunder[s:s + dur] = True
    for s, dur, extra in spec["gusts"]:
        gust_bump[s:s + dur] += extra

    raining = (precip > 0.1).astype(float)

    # --- temperature: daily wave (warmest at 15:00) + day offset + noise ---
    offsets = np.array(spec["offsets"])[day]
    temp = (spec["t_mean"] + offsets
            + spec["t_amp"] * np.sin(2 * np.pi * (hod - 9) / 24)
            + rng.normal(0, 0.4, n) - 2.5 * raining)

    # --- humidity falls when it is hot, rises when it rains ---
    humidity = np.clip(spec["hum"] - 1.5 * (temp - spec["t_mean"])
                       + 5 * raining + rng.normal(0, 1.5, n), 15, 99)

    # --- wind and gusts ---
    wind = np.clip(spec["wind"] + np.sin(2 * np.pi * (hod - 14) / 24)
                   + rng.normal(0, 0.5, n), 0.5, None)
    gust = np.maximum(wind * 1.4 + 1.0 + gust_bump, wind)

    # --- UV: bell curve between 06:00 and 18:00, lower when stormy ---
    uv = spec["uv_peak"] * np.clip(np.sin(np.pi * (hod - 6) / 12), 0, None) ** 1.3
    uv = np.round(uv * (1 - 0.7 * raining), 1)

    # --- simple "feels like": muggy air feels hotter ---
    feels = temp + 0.025 * np.clip(humidity - 40, 0, None) * np.clip(temp - 26, 0, None)

    condition = [_describe(t, r, th, h) for t, r, th, h in zip(temp, precip, thunder, humidity)]

    hourly = pd.DataFrame({
        "time": times,
        "temp_c": temp.round(1),
        "feels_c": feels.round(1),
        "humidity_pct": humidity.round(0),
        "wind_ms": wind.round(1),
        "gust_ms": gust.round(1),
        "precip_mm": precip.round(2),
        "precip_prob_pct": prob.round(0),
        "uv_index": uv,
        "condition": condition,
        "is_thunder": thunder,
        "step_hours": 1,
    })[HOURLY_COLUMNS]

    now = pd.Timestamp(config.SIM_NOW)
    row = hourly[hourly["time"] == now].iloc[0]
    current = {"time": now, "temp_c": row["temp_c"], "feels_c": row["feels_c"],
               "humidity_pct": row["humidity_pct"], "wind_ms": row["wind_ms"],
               "gust_ms": row["gust_ms"], "precip_mm": row["precip_mm"],
               "condition": row["condition"]}

    return WeatherBundle(city=city, country=country, lat=lat, lon=lon,
                         source="simulation", now=now, current=current, hourly=hourly,
                         notes=["Simulated data: illustrative scenario, not a real forecast."])


def load_sample_bundles(cities=None):
    """Simulate all sample cities (or only the ones named in `cities`)."""
    table = pd.read_csv(config.SAMPLE_CITIES_CSV)
    if cities:
        wanted = [c.strip().lower() for c in cities]
        known = {c.lower(): c for c in table["city"]}
        missing = [c for c in wanted if c not in known]
        if missing:
            raise ValueError(f"Unknown simulation city: {missing}. "
                             f"Available: {', '.join(table['city'])}")
        table = table[table["city"].str.lower().isin(wanted)]
    return [simulate_city(r.city, r.country, r.lat, r.lon, r.scenario, seed=i)
            for i, r in enumerate(table.itertuples())]
