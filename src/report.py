"""
report.py - saves CSV/JSON tables and one readable text report.
"""
import json
from datetime import datetime

import pandas as pd

from src import analysis, config
from src.alerts import SEVERITY_RANK


def alert_line(a, short=False):
    """One alert as a single line of text (short = only the first sentence)."""
    message = a.message.split(". ")[0].rstrip(".") + "." if short else a.message
    return f"[{a.severity.upper()}] {a.city} - {a.title}: {message}"


def save_tables(bundles, alerts, folder=None):
    """Write CSV/JSON files to outputs/. Returns the paths."""
    folder = folder or config.OUTPUT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    daily = pd.concat([analysis.daily_summary(b) for b in bundles], ignore_index=True)
    alert_rows = [a.to_dict() for a in alerts]
    alert_cols = ["city", "category", "severity", "title", "message", "time"]

    files = {
        "current_weather.csv": analysis.current_table(bundles),
        "hourly_forecast.csv": analysis.all_hourly(bundles),
        "daily_forecast.csv": daily,
        "alerts.csv": pd.DataFrame(alert_rows, columns=alert_cols),
    }
    paths = []
    for name, table in files.items():
        path = folder / name
        table.to_csv(path, index=False)
        paths.append(path)
    json_path = folder / "alerts.json"
    json_path.write_text(json.dumps(alert_rows, indent=2), encoding="utf-8")
    paths.append(json_path)
    return paths


def _fmt(value, template, unit=""):
    """Format a number, or 'n/a' when the source did not provide it."""
    if value is None or pd.isna(value):
        return "n/a"
    return template.format(value) + unit


def build_text_report(bundles, alerts, mode_label, th):
    """Return the full text report as one string."""
    line = "=" * 70
    out = [line, "WEATHER FORECAST & ALERT REPORT", line,
           f"Generated on : {datetime.now():%Y-%m-%d %H:%M}",
           f"Mode         : {mode_label}",
           f"Cities       : {', '.join(b.city for b in bundles)}", ""]

    for b in bundles:
        c = b.current
        s = analysis.forecast_summary(b)
        out += [f"{b.city.upper()} ({b.country})   source: {b.source}   as of {b.now:%Y-%m-%d %H:%M} local time",
                "-" * 70,
                f"Now          : {_fmt(c['temp_c'], '{:.1f}', 'C')} (feels like {_fmt(c['feels_c'], '{:.1f}', 'C')}), "
                f"humidity {_fmt(c['humidity_pct'], '{:.0f}', '%')}, wind {_fmt(c['wind_ms'], '{:.1f}', ' m/s')}, "
                f"{c['condition']}"]
        if s:
            rain = f"{s['rain_total_mm']:.0f} mm"
            if s["rain_start"] is not None:
                rain += f" (from {s['rain_start']:%d %b %H:%M})"
            out += [f"Next 48 h    : hottest {s['hottest_c']:.1f}C at {s['hottest_time']:%d %b %H:%M}, "
                    f"coolest {s['coolest_c']:.1f}C at {s['coolest_time']:%d %b %H:%M}",
                    f"               rain {rain}, max chance {s['max_rain_chance_pct']:.0f}%",
                    f"               strongest gust {s['max_gust_ms']:.1f} m/s ({s['max_gust_ms'] * 3.6:.0f} km/h), "
                    f"thunderstorm {s['thunder_hours']:.0f} h"]
        daily = analysis.daily_summary(b)
        out += ["", "Daily outlook (full days; hours already passed are included):"]
        out += ["  " + row for row in daily.drop(columns="city").rename(columns={
            "temp_max_c": "max_C", "temp_min_c": "min_C", "rain_mm": "rain_mm",
            "rain_chance_max_pct": "rain_%", "gust_max_ms": "gust_ms",
            "humidity_avg_pct": "humid_%", "uv_max": "uv_max"}).to_string(index=False).splitlines()]
        mine = [a for a in alerts if a.city == b.city]
        out += ["", "Alerts:"]
        out += [f"  {alert_line(a)}" for a in mine] if mine else ["  None - conditions look calm."]
        out.append("")

    counts = {k: sum(1 for a in alerts if a.severity == k) for k in SEVERITY_RANK}
    out += [line, "ALERT SUMMARY", line,
            f"Total alerts : {len(alerts)}  (critical {counts['critical']}, "
            f"warning {counts['warning']}, info {counts['info']})",
            "", "Thresholds used:",
            f"  Heat            warning {th.heat_warn_c:.0f}C, critical {th.heat_critical_c:.0f}C (next 48 h)",
            f"  Rain            chance >= {th.rain_prob_warn_pct:.0f}% (next 12 h); "
            f"heavy rain >= {th.heavy_rain_24h_mm:.0f} mm (next 24 h)",
            f"  Wind gusts      warning {th.gust_warn_ms:.0f} m/s, critical {th.gust_critical_ms:.0f} m/s (next 24 h)",
            f"  Humidity        average >= {th.humidity_warn_pct:.0f}% (next 12 h)",
            f"  UV index        warning {th.uv_warn:.0f}, critical {th.uv_critical:.0f} (rest of today)",
            f"  Thunderstorm    any in next 24 h; critical from {th.thunder_critical_hours} h"]
    notes = []
    for b in bundles:
        for n in b.notes:
            if n not in notes:
                notes.append(n)
    if notes:
        out += ["", "Notes:"] + [f"  - {n}" for n in notes]
    out.append(line)
    return "\n".join(out)


def save_text_report(bundles, alerts, mode_label, th, folder=None):
    """Write the text report to reports/weather_report.txt."""
    folder = folder or config.REPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "weather_report.txt"
    path.write_text(build_text_report(bundles, alerts, mode_label, th), encoding="utf-8")
    return path
