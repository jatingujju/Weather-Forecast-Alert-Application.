"""
main.py - run the Weather Forecast & Alert Application.

    python main.py                                   # simulation mode, all sample cities
    python main.py --city Mumbai --city Delhi        # simulation, chosen cities
    python main.py --mode api --city Pune            # LIVE weather (Open-Meteo, no key)
    python main.py --mode api --provider openweathermap --city "Pune,IN"   # needs .env key
    python main.py --heat-warn 35 --rain-prob 50     # change alert thresholds
    python main.py --notify                          # also email warning/critical alerts
"""
import argparse
import sys

import pandas as pd

from src import alerts as alert_engine
from src import analysis, config, notify, providers, report, simulator, visualize
from src.config import Thresholds


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Weather Forecast & Alert Application")
    p.add_argument("--mode", choices=["simulation", "api"], default="simulation",
                   help="simulation = fake data, no internet (default); api = live weather")
    p.add_argument("--city", action="append",
                   help="city name; repeat the option for several cities")
    p.add_argument("--provider", choices=["open-meteo", "openweathermap"], default="open-meteo",
                   help="live data provider (api mode only)")
    p.add_argument("--heat-warn", type=float, help="heat warning limit in C")
    p.add_argument("--heat-critical", type=float, help="extreme heat limit in C")
    p.add_argument("--rain-prob", type=float, help="rain chance limit in %%")
    p.add_argument("--gust-warn", type=float, help="wind gust warning limit in m/s")
    p.add_argument("--humidity-warn", type=float, help="average humidity limit in %%")
    p.add_argument("--notify", action="store_true", help="email warning/critical alerts")
    return p.parse_args(argv)


def build_thresholds(args):
    th = Thresholds()
    if args.heat_warn is not None:
        th.heat_warn_c = args.heat_warn
    if args.heat_critical is not None:
        th.heat_critical_c = args.heat_critical
    if args.rain_prob is not None:
        th.rain_prob_warn_pct = args.rain_prob
    if args.gust_warn is not None:
        th.gust_warn_ms = args.gust_warn
    if args.humidity_warn is not None:
        th.humidity_warn_pct = args.humidity_warn
    return th


def get_bundles(args):
    """Get weather for every requested city (simulation or live)."""
    if args.mode == "simulation":
        return simulator.load_sample_bundles(args.city)

    cities = args.city or ["Mumbai"]
    bundles = []
    for city in cities:
        try:
            if args.provider == "openweathermap":
                bundles.append(providers.fetch_openweathermap(city, config.get_setting("OPENWEATHER_API_KEY")))
            else:
                bundles.append(providers.fetch_open_meteo(city, config.FORECAST_DAYS))
        except providers.WeatherError as error:
            print(f"          ! {city}: {error}")
    return bundles


def _shown(path):
    """Path as text, relative to the project folder when possible."""
    try:
        return str(path.relative_to(config.BASE_DIR))
    except ValueError:
        return str(path)


def _num(value, template, unit=""):
    return "n/a" if value is None or pd.isna(value) else template.format(value) + unit


def print_current_table(bundles):
    print(f"          {'City':<12}{'Temp':>8}{'Feels':>8}{'Humid':>7}{'Wind':>9}   Condition")
    for b in bundles:
        c = b.current
        print(f"          {b.city:<12}{_num(c['temp_c'], '{:.1f}', 'C'):>8}"
              f"{_num(c['feels_c'], '{:.1f}', 'C'):>8}{_num(c['humidity_pct'], '{:.0f}', '%'):>7}"
              f"{_num(c['wind_ms'], '{:.1f}', 'm/s'):>9}   {c['condition']}")


def main(argv=None):
    args = parse_args(argv)
    config.load_env()
    th = build_thresholds(args)
    mode_label = "simulation (fake data, fixed demo clock)" if args.mode == "simulation" \
        else f"live API ({args.provider})"

    print(f"STEP 1/5  Getting weather data - {mode_label}")
    try:
        bundles = get_bundles(args)
    except ValueError as error:
        print(f"          ! {error}")
        return 2
    if not bundles:
        print("          ! No weather data could be loaded. See the messages above.")
        return 1
    print(f"          loaded {len(bundles)} city/cities: {', '.join(b.city for b in bundles)}")

    print("STEP 2/5  Current weather")
    print_current_table(bundles)

    print("STEP 3/5  Checking alert rules")
    alerts = alert_engine.evaluate_all(bundles, th)
    if alerts:
        for a in alerts:
            print(f"          {report.alert_line(a, short=True)}")
    else:
        print("          No alerts - conditions look calm.")

    print("STEP 4/5  Saving tables and charts")
    for path in report.save_tables(bundles, alerts):
        print(f"          saved {_shown(path)}")
    charts = visualize.save_all_charts(bundles, alerts, th)
    print(f"          saved {len(charts)} charts in images/")

    print("STEP 5/5  Writing the text report")
    report_path = report.save_text_report(bundles, alerts, mode_label, th)
    print(f"          saved {_shown(report_path)}")

    counts = {k: sum(1 for a in alerts if a.severity == k) for k in alert_engine.SEVERITY_RANK}
    print(f"\nDONE. {len(alerts)} alert(s): {counts['critical']} critical, "
          f"{counts['warning']} warning, {counts['info']} info.")
    if args.notify:
        print("NOTIFY    " + notify.send_alerts(alerts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
