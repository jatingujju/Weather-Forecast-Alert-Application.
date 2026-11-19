"""
visualize.py - the charts. Every plot_* function RETURNS a matplotlib Figure
(so Streamlit can show it too); save_all_charts() writes the PNG files.
"""
import matplotlib

matplotlib.use("Agg")  # draw without opening windows
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from src import analysis, config
from src.alerts import CATEGORIES, window
from src.config import Thresholds

sns.set_theme(style="whitegrid")
DATE_FORMAT = mdates.DateFormatter("%d %b\n%H:%M")


def _next_hours(bundle, hours=48):
    return window(bundle.hourly, bundle.now, hours)


def plot_temperature_comparison(bundles, th=None):
    """Chart 1: temperature of every city for the next 48 hours."""
    th = th or Thresholds()
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for b in bundles:
        w = _next_hours(b)
        ax.plot(w["time"], w["temp_c"], linewidth=2, label=b.city)
    ax.axhline(th.heat_warn_c, color="orange", linestyle="--", linewidth=1.2,
               label=f"Heat warning ({th.heat_warn_c:.0f}°C)")
    ax.axhline(th.heat_critical_c, color="red", linestyle="--", linewidth=1.2,
               label=f"Extreme heat ({th.heat_critical_c:.0f}°C)")
    ax.set_title("Temperature forecast - next 48 hours", fontsize=14, weight="bold")
    ax.set_ylabel("Temperature (°C)")
    ax.xaxis.set_major_formatter(DATE_FORMAT)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    fig.tight_layout()
    return fig


def plot_rain_comparison(bundles, th=None):
    """Chart 2: total rain expected in the next 24 hours per city."""
    th = th or Thresholds()
    names = [b.city for b in bundles]
    totals = [window(b.hourly, b.now, 24)["precip_mm"].sum() for b in bundles]
    colors = ["#d62728" if t >= th.heavy_rain_24h_mm else "#1f77b4" for t in totals]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(names, totals, color=colors)
    for i, t in enumerate(totals):
        ax.text(i, t, f"{t:.0f} mm", ha="center", va="bottom", fontsize=10)
    ax.axhline(th.heavy_rain_24h_mm, color="red", linestyle="--", linewidth=1.2,
               label=f"Heavy rain limit ({th.heavy_rain_24h_mm:.0f} mm)")
    ax.set_title("Rain expected in the next 24 hours", fontsize=14, weight="bold")
    ax.set_ylabel("Rain (mm)")
    ax.set_ylim(0, max(max(totals), th.heavy_rain_24h_mm) * 1.2)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_wind_comparison(bundles, th=None):
    """Chart 3: strongest wind gust in the next 24 hours per city (km/h)."""
    th = th or Thresholds()
    names = [b.city for b in bundles]
    gusts = [window(b.hourly, b.now, 24)["gust_ms"].max() * 3.6 for b in bundles]
    colors = ["#d62728" if g >= th.gust_critical_ms * 3.6
              else "#ff7f0e" if g >= th.gust_warn_ms * 3.6 else "#2ca02c" for g in gusts]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(names, gusts, color=colors)
    for i, g in enumerate(gusts):
        ax.text(i, g, f"{g:.0f}", ha="center", va="bottom", fontsize=10)
    ax.axhline(th.gust_warn_ms * 3.6, color="orange", linestyle="--", linewidth=1.2,
               label=f"Warning ({th.gust_warn_ms * 3.6:.0f} km/h)")
    ax.axhline(th.gust_critical_ms * 3.6, color="red", linestyle="--", linewidth=1.2,
               label=f"Critical ({th.gust_critical_ms * 3.6:.0f} km/h)")
    ax.set_title("Strongest wind gust in the next 24 hours", fontsize=14, weight="bold")
    ax.set_ylabel("Wind gust (km/h)")
    ax.set_ylim(0, max(max(gusts), th.gust_critical_ms * 3.6) * 1.2)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_alert_matrix(alerts, cities):
    """Chart 4: which city has which alert, coloured by severity."""
    matrix = analysis.alert_matrix(alerts, cities)
    names = {0: "-", 1: "INFO", 2: "WARNING", 3: "CRITICAL"}
    # (plain numpy lookup: works the same for one city or many, in any pandas version)
    labels = pd.DataFrame(np.vectorize(names.get)(matrix.to_numpy()),
                          index=matrix.index, columns=matrix.columns)
    cmap = ListedColormap(["#f0f0f0", "#9ecae1", "#fdae6b", "#e6550d"])
    fig, ax = plt.subplots(figsize=(10, 0.7 * len(cities) + 2.5))
    sns.heatmap(matrix, annot=labels, fmt="", cmap=cmap, vmin=0, vmax=3, cbar=False,
                linewidths=2, linecolor="white", ax=ax, annot_kws={"fontsize": 9})
    ax.set_title("Alert overview by city", fontsize=14, weight="bold", pad=28)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.xaxis.tick_top()
    ax.legend(handles=[Patch(color="#f0f0f0", label="No alert"), Patch(color="#9ecae1", label="Info"),
                       Patch(color="#fdae6b", label="Warning"), Patch(color="#e6550d", label="Critical")],
              loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=4, frameon=False)
    fig.tight_layout()
    return fig


def plot_city_dashboard(bundle, th=None):
    """Chart 5: four-panel detail view of one city for the next 48 hours."""
    th = th or Thresholds()
    w = _next_hours(bundle)
    step = float(w["step_hours"].iloc[0]) if not w.empty else 1.0
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    (ax_t, ax_h), (ax_r, ax_w) = axes

    ax_t.plot(w["time"], w["temp_c"], color="#d62728", linewidth=2, label="Temperature")
    ax_t.plot(w["time"], w["feels_c"], color="#ff9896", linewidth=1.5, linestyle="--", label="Feels like")
    ax_t.axhline(th.heat_warn_c, color="orange", linestyle=":", linewidth=1)
    ax_t.set_title("Temperature (°C)", weight="bold")
    ax_t.legend(loc="upper right")

    ax_h.plot(w["time"], w["humidity_pct"], color="#1f77b4", linewidth=2)
    ax_h.fill_between(w["time"], w["humidity_pct"], alpha=0.15, color="#1f77b4")
    ax_h.axhline(th.humidity_warn_pct, color="orange", linestyle=":", linewidth=1)
    ax_h.set_ylim(0, 100)
    ax_h.set_title("Humidity (%)", weight="bold")

    ax_r.bar(w["time"], w["precip_mm"], width=step / 24, color="#4c72b0", label="Rain (mm per step)")
    ax_r.set_ylabel("Rain (mm)")
    ax_p = ax_r.twinx()
    ax_p.plot(w["time"], w["precip_prob_pct"], color="#dd8452", linewidth=2, label="Chance of rain (%)")
    ax_p.set_ylim(0, 125)                 # headroom so the legend hides nothing
    ax_p.set_yticks([0, 20, 40, 60, 80, 100])
    ax_p.set_ylabel("Chance (%)")
    ax_p.grid(False)
    ax_r.set_title("Rain and chance of rain", weight="bold")
    lines = ax_r.get_legend_handles_labels()[0] + ax_p.get_legend_handles_labels()[0]
    names = ax_r.get_legend_handles_labels()[1] + ax_p.get_legend_handles_labels()[1]
    ax_r.legend(lines, names, loc="upper right")

    ax_w.plot(w["time"], w["wind_ms"], color="#2ca02c", linewidth=2, label="Wind")
    ax_w.plot(w["time"], w["gust_ms"], color="#98df8a", linewidth=1.5, linestyle="--", label="Gusts")
    ax_w.axhline(th.gust_warn_ms, color="orange", linestyle=":", linewidth=1)
    ax_w.set_title("Wind (m/s)", weight="bold")
    ax_w.legend(loc="upper right")

    for ax in (ax_t, ax_h, ax_r, ax_w):
        ax.xaxis.set_major_formatter(DATE_FORMAT)
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle(f"{bundle.city} - next 48 hours  ({bundle.source})", fontsize=15, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def _slug(name):
    return name.lower().replace(" ", "_").replace(",", "")


def save_all_charts(bundles, alerts, th=None, folder=None):
    """Draw every chart and save it as a PNG. Returns the list of file paths."""
    th = th or Thresholds()
    folder = folder or config.IMAGE_DIR
    (folder / "cities").mkdir(parents=True, exist_ok=True)
    jobs = [
        (folder / "01_temperature_comparison.png", plot_temperature_comparison(bundles, th)),
        (folder / "02_rain_24h_comparison.png", plot_rain_comparison(bundles, th)),
        (folder / "03_wind_gust_comparison.png", plot_wind_comparison(bundles, th)),
        (folder / "04_alert_matrix.png", plot_alert_matrix(alerts, [b.city for b in bundles])),
    ]
    for b in bundles:
        jobs.append((folder / "cities" / f"{_slug(b.city)}_dashboard.png", plot_city_dashboard(b, th)))
    saved = []
    for path, fig in jobs:
        fig.savefig(path, dpi=140)
        plt.close(fig)
        saved.append(path)
    return saved
