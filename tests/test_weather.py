"""
Tests for the Weather Forecast & Alert Application.
Run with:  python -m pytest      (or run this file's functions directly)

The sample API responses in tests/fixtures are hand-made to look like the
documented Open-Meteo / OpenWeatherMap formats. They check our PARSING code;
they do not prove the live services behave exactly the same.
"""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import main as main_module
from src import alerts as A
from src import analysis, config, notify, providers, report, simulator
from src.config import Thresholds
from src.models import HOURLY_COLUMNS, WeatherBundle

FIX = Path(__file__).parent / "fixtures"
NOW = pd.Timestamp("2026-11-18 09:00")


def load(name):
    return json.loads((FIX / name).read_text())


def calm_bundle(changes=None):
    """Calm weather around NOW; `changes` = {hours_from_now: {column: value}}."""
    times = pd.date_range(NOW - pd.Timedelta(hours=9), periods=72, freq="h")
    df = pd.DataFrame({"time": times, "temp_c": 28.0, "feels_c": 28.0, "humidity_pct": 60.0,
                       "wind_ms": 3.0, "gust_ms": 5.0, "precip_mm": 0.0, "precip_prob_pct": 5.0,
                       "uv_index": 3.0, "condition": "Clear", "is_thunder": False, "step_hours": 1})[HOURLY_COLUMNS]
    for hours_from_now, cols in (changes or {}).items():
        idx = df.index[df["time"] == NOW + pd.Timedelta(hours=hours_from_now)][0]
        for col, val in cols.items():
            df.loc[idx, col] = val
    return WeatherBundle("Testville", "XX", 0, 0, "test", NOW, {}, df)


class FakeResponse:
    def __init__(self, status=200, data=None, bad_json=False):
        self.status_code, self._data, self._bad = status, data, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._data


# ---------------------------------------------------------------- simulation
def test_simulation_is_reproducible_and_complete():
    a, b = simulator.load_sample_bundles(), simulator.load_sample_bundles()
    assert len(a) == 6
    pd.testing.assert_frame_equal(a[0].hourly, b[0].hourly)
    assert list(a[0].hourly.columns) == HOURLY_COLUMNS
    assert len(a[0].hourly) == config.SIM_HOURS
    assert a[0].hourly["time"].is_monotonic_increasing


def test_simulation_unknown_city_gives_helpful_error():
    try:
        simulator.load_sample_bundles(["Atlantis"])
        assert False, "should raise"
    except ValueError as err:
        assert "Atlantis".lower() in str(err).lower() and "Available" in str(err)


def test_simulation_scenarios_fire_expected_alerts():
    found = {b.city: {(a.category, a.severity) for a in A.evaluate(b)} for b in simulator.load_sample_bundles()}
    assert ("Rain", "critical") in found["Mumbai"]
    assert ("Heat", "critical") in found["Delhi"]
    assert {("Rain", "critical"), ("Wind", "critical"), ("Thunderstorm", "critical")} <= found["Chennai"]
    assert found["Bengaluru"] == set()                      # calm city -> no alerts
    assert ("UV", "critical") in found["Jaipur"]


# ---------------------------------------------------------------- rules
def test_calm_weather_has_no_alerts():
    assert A.evaluate(calm_bundle()) == []


def test_heat_levels_and_custom_threshold():
    assert A.evaluate(calm_bundle({5: {"temp_c": 38.0}}))[0].severity == "warning"
    assert A.evaluate(calm_bundle({5: {"temp_c": 41.0}}))[0].severity == "critical"
    assert A.evaluate(calm_bundle({5: {"temp_c": 31.0}})) == []
    assert A.evaluate(calm_bundle({5: {"temp_c": 31.0}}), Thresholds(heat_warn_c=30.0))[0].category == "Heat"


def test_heat_after_48h_is_ignored():
    assert A.evaluate(calm_bundle({50: {"temp_c": 45.0}})) == []


def test_rain_chance_is_only_checked_for_next_12_hours():
    assert [a.title for a in A.evaluate(calm_bundle({6: {"precip_prob_pct": 80.0}}))] == ["Rain likely"]
    assert A.evaluate(calm_bundle({13: {"precip_prob_pct": 95.0}})) == []


def test_heavy_rain_uses_24h_total():
    b = calm_bundle({10: {"precip_mm": 30.0}, 11: {"precip_mm": 30.0}})
    alert = A.evaluate(b)[0]
    assert alert.title == "Heavy rain" and alert.severity == "critical"
    assert A.evaluate(calm_bundle({30: {"precip_mm": 90.0}})) == []        # beyond 24 h


def test_rain_rule_works_with_3_hour_steps():
    b = calm_bundle()
    b.hourly = b.hourly[b.hourly["time"].dt.hour % 3 == 0].reset_index(drop=True)
    b.hourly["step_hours"] = 3
    b.hourly.loc[b.hourly["time"] == NOW + pd.Timedelta(hours=3), "precip_mm"] = 28.0
    b.hourly.loc[b.hourly["time"] == NOW + pd.Timedelta(hours=6), "precip_mm"] = 28.0
    assert A.evaluate(b)[0].title == "Heavy rain"


def test_wind_levels():
    assert A.evaluate(calm_bundle({4: {"gust_ms": 16.0}}))[0].severity == "warning"
    assert A.evaluate(calm_bundle({4: {"gust_ms": 21.0}}))[0].severity == "critical"


def test_thunderstorm_hours_decide_severity():
    two = calm_bundle({4: {"is_thunder": True}, 5: {"is_thunder": True}})
    four = calm_bundle({4: {"is_thunder": True}, 5: {"is_thunder": True}, 6: {"is_thunder": True}, 7: {"is_thunder": True}})
    assert A.evaluate(two)[0].severity == "warning"
    assert A.evaluate(four)[0].severity == "critical"


def test_humidity_is_info_and_uses_average():
    b = calm_bundle()
    b.hourly.loc[(b.hourly["time"] >= NOW) & (b.hourly["time"] < NOW + pd.Timedelta(hours=12)), "humidity_pct"] = 90.0
    alert = A.evaluate(b)[0]
    assert alert.category == "Humidity" and alert.severity == "info"


def test_uv_only_for_rest_of_today_and_skips_missing_values():
    assert A.evaluate(calm_bundle({3: {"uv_index": 9.0}}))[0].category == "UV"
    assert A.evaluate(calm_bundle({20: {"uv_index": 9.0}})) == []       # tomorrow
    no_uv = calm_bundle({3: {"uv_index": 9.0}})
    no_uv.hourly["uv_index"] = np.nan                                      # provider without UV
    assert A.evaluate(no_uv) == []
    evening = calm_bundle({-2: {"uv_index": 11.0}})                      # peak already passed
    assert A.evaluate(evening) == []


def test_alerts_sorted_most_severe_first():
    b = calm_bundle({5: {"temp_c": 41.0}, 6: {"humidity_pct": 99.0}, 4: {"gust_ms": 16.0}})
    order = [a.severity for a in A.evaluate(b)]
    assert order == sorted(order, key=lambda s: -A.SEVERITY_RANK[s])


# ---------------------------------------------------------------- Open-Meteo
def test_parse_open_meteo_fixture():
    bundle = providers.parse_open_meteo(load("open_meteo_forecast.json"), "Pune", "IN", 18.5, 73.9)
    h = bundle.hourly
    assert list(h.columns) == HOURLY_COLUMNS and len(h) == 48
    assert bundle.now == pd.Timestamp("2026-11-18 09:15")
    assert h["precip_prob_pct"].notna().all()                       # nulls became 0
    assert h["uv_index"].isna().any() and h["uv_index"].notna().any()
    assert bool(h.loc[16, "is_thunder"]) and h.loc[14, "condition"] == "Light rain"
    cats = {a.category for a in A.evaluate(bundle)}
    assert {"Heat", "Thunderstorm", "Wind"} <= cats


def test_parse_open_meteo_rejects_bad_payload():
    try:
        providers.parse_open_meteo({"hourly": {}}, "X", "", 0, 0)
        assert False
    except providers.WeatherError as err:
        assert "unexpected format" in str(err)


def test_geocode_city_not_found_and_found():
    original = providers.requests.get
    try:
        providers.requests.get = lambda *a, **k: FakeResponse(200, {"generationtime_ms": 0.5})
        try:
            providers.geocode_open_meteo("Nowhereville")
            assert False
        except providers.WeatherError as err:
            assert "not found" in str(err).lower()
        providers.requests.get = lambda *a, **k: FakeResponse(200, load("open_meteo_geocode.json"))
        place = providers.geocode_open_meteo("Pune,IN")
        assert place["name"] == "Pune" and abs(place["lat"] - 18.52) < 0.1
    finally:
        providers.requests.get = original


# ---------------------------------------------------------------- OpenWeatherMap
def test_parse_openweathermap_fixture():
    bundle = providers.parse_openweathermap(load("owm_current.json"), load("owm_forecast.json"))
    h = bundle.hourly
    assert bundle.city == "Pune" and bundle.source == "openweathermap"
    assert bundle.now == pd.Timestamp("2026-11-18 15:30")             # UTC 10:00 + 5h30
    assert h.loc[0, "time"] == pd.Timestamp("2026-11-18 15:30")
    assert (h["step_hours"] == 3).all() and h["uv_index"].isna().all()
    assert h.loc[1, "precip_prob_pct"] == 80 and h.loc[1, "precip_mm"] == 6.5
    assert bool(h.loc[2, "is_thunder"]) and not bool(h.loc[0, "is_thunder"])
    assert any("UV" in n for n in bundle.notes)
    assert {"Thunderstorm", "Wind", "Rain"} <= {a.category for a in A.evaluate(bundle)}


def test_openweathermap_requires_key():
    try:
        providers.fetch_openweathermap("Pune", None)
        assert False
    except providers.WeatherError as err:
        assert "OPENWEATHER_API_KEY" in str(err)


# ---------------------------------------------------------------- HTTP errors
def _error_message(status=None, exception=None, bad_json=False):
    original = providers.requests.get

    def fake(*a, **k):
        if exception:
            raise exception("http://x/?appid=SECRET123")
        return FakeResponse(status, {}, bad_json)
    providers.requests.get = fake
    try:
        providers._get_json("http://x", {"appid": "SECRET123"}, sleep=lambda s: None)
    except providers.WeatherError as err:
        return str(err)
    finally:
        providers.requests.get = original
    return None


def test_http_errors_become_friendly_messages_without_leaking_the_key():
    msgs = {
        "401": _error_message(401), "404": _error_message(404), "429": _error_message(429),
        "500": _error_message(503), "odd": _error_message(418), "json": _error_message(200, bad_json=True),
        "net": _error_message(exception=providers.requests.exceptions.ConnectionError),
        "slow": _error_message(exception=providers.requests.exceptions.Timeout),
    }
    assert "key was rejected" in msgs["401"] and "not found" in msgs["404"]
    assert "Too many" in msgs["429"] and "having problems" in msgs["500"]
    assert "418" in msgs["odd"] and "valid JSON" in msgs["json"]
    assert "internet" in msgs["net"] and "internet" in msgs["slow"]
    assert all("SECRET123" not in m for m in msgs.values())


def test_server_error_is_retried_then_succeeds():
    original, calls = providers.requests.get, []

    def flaky(*a, **k):
        calls.append(1)
        return FakeResponse(503) if len(calls) < 3 else FakeResponse(200, {"ok": True})
    providers.requests.get = flaky
    try:
        assert providers._get_json("http://x", {}, retries=2, sleep=lambda s: None) == {"ok": True}
        assert len(calls) == 3
    finally:
        providers.requests.get = original


# ---------------------------------------------------------------- .env and notify
def test_load_env_reads_values_and_keeps_existing():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ".env"
        path.write_text('# comment\nTEST_KEY_ONE="abc123"\nTEST_KEY_TWO = hello\n\nTEST_EXISTING=new\nbroken line\n')
        os.environ["TEST_EXISTING"] = "old"
        try:
            loaded = config.load_env(path)
            assert os.environ["TEST_KEY_ONE"] == "abc123" and os.environ["TEST_KEY_TWO"] == "hello"
            assert os.environ["TEST_EXISTING"] == "old" and "TEST_EXISTING" not in loaded
        finally:
            for k in ("TEST_KEY_ONE", "TEST_KEY_TWO", "TEST_EXISTING"):
                os.environ.pop(k, None)
    assert config.load_env(Path("does-not-exist.env")) == []


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def starttls(self, context=None): pass
    def login(self, user, password): FakeSMTP.login_used = (user, password)
    def send_message(self, msg): FakeSMTP.sent.append(msg)


def test_email_dry_run_then_real_send_with_deduplication():
    alerts = A.evaluate(calm_bundle({5: {"temp_c": 41.0}, 6: {"humidity_pct": 99.0}}))
    names = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO"]
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "alert_log.csv"
        for n in names:
            os.environ.pop(n, None)
        assert "[DRY RUN]" in notify.send_alerts(alerts, log_path=log)
        assert not log.exists()                                       # dry run records nothing
        os.environ.update(SMTP_HOST="smtp.test", SMTP_USER="me@test", SMTP_PASSWORD="pw", ALERT_EMAIL_TO="you@test")
        try:
            now = pd.Timestamp("2026-11-18 10:00")
            status = notify.send_alerts(alerts, log_path=log, now=now, smtp_factory=FakeSMTP)
            assert "Email sent" in status and len(FakeSMTP.sent) == 1
            assert "Extreme heat" in FakeSMTP.sent[0].get_content()
            assert "Very humid" not in FakeSMTP.sent[0].get_content()   # info alerts are not emailed
            assert "No new" in notify.send_alerts(alerts, log_path=log, now=now + pd.Timedelta(hours=2), smtp_factory=FakeSMTP)
            assert "Email sent" in notify.send_alerts(alerts, log_path=log, now=now + pd.Timedelta(hours=13), smtp_factory=FakeSMTP)
        finally:
            for n in names:
                os.environ.pop(n, None)


def test_email_failure_does_not_leak_password():
    class BrokenSMTP(FakeSMTP):
        def login(self, user, password):
            import smtplib
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
    alerts = A.evaluate(calm_bundle({5: {"temp_c": 41.0}}))
    os.environ.update(SMTP_HOST="smtp.test", SMTP_USER="me@test", SMTP_PASSWORD="topsecret", ALERT_EMAIL_TO="you@test")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            status = notify.send_alerts(alerts, log_path=Path(tmp) / "log.csv", smtp_factory=BrokenSMTP)
        assert "failed" in status and "topsecret" not in status
    finally:
        for n in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO"):
            os.environ.pop(n, None)


# ---------------------------------------------------------------- reports and main
def test_alert_matrix_values():
    bundles = simulator.load_sample_bundles(["Mumbai", "Bengaluru"])
    m = analysis.alert_matrix(A.evaluate_all(bundles), ["Mumbai", "Bengaluru"])
    assert m.loc["Mumbai", "Rain"] == 3 and m.loc["Bengaluru"].sum() == 0


def test_report_files_are_created_even_with_no_alerts():
    bundles = simulator.load_sample_bundles(["Bengaluru"])
    with tempfile.TemporaryDirectory() as tmp:
        out, rep = Path(tmp) / "o", Path(tmp) / "r"
        paths = report.save_tables(bundles, [], out)
        assert (out / "alerts.csv").read_text().startswith("city,category,severity")
        assert json.loads((out / "alerts.json").read_text()) == [] and len(paths) == 5
        text = report.build_text_report(bundles, [], "test", Thresholds())
        assert "None - conditions look calm." in text and "Total alerts : 0" in text
        assert report.save_text_report(bundles, [], "test", Thresholds(), rep).exists()


def test_main_end_to_end_and_error_codes():
    saved = (config.OUTPUT_DIR, config.IMAGE_DIR, config.REPORT_DIR)
    with tempfile.TemporaryDirectory() as tmp:
        config.OUTPUT_DIR, config.IMAGE_DIR, config.REPORT_DIR = (Path(tmp) / "o", Path(tmp) / "i", Path(tmp) / "r")
        try:
            assert main_module.main(["--city", "Mumbai", "--heat-warn", "20"]) == 0
            assert (Path(tmp) / "r" / "weather_report.txt").exists()
            assert (Path(tmp) / "i" / "cities" / "mumbai_dashboard.png").exists()
            assert "Heat" in (Path(tmp) / "o" / "alerts.csv").read_text()      # custom threshold worked
            assert main_module.main(["--city", "Atlantis"]) == 2                # unknown simulation city
        finally:
            config.OUTPUT_DIR, config.IMAGE_DIR, config.REPORT_DIR = saved


def test_api_mode_reports_errors_and_returns_code_1():
    original = providers.requests.get
    providers.requests.get = lambda *a, **k: FakeResponse(404, {})
    saved = (config.OUTPUT_DIR, config.IMAGE_DIR, config.REPORT_DIR)
    try:
        assert main_module.main(["--mode", "api", "--city", "Nowhereville"]) == 1
    finally:
        providers.requests.get = original
        config.OUTPUT_DIR, config.IMAGE_DIR, config.REPORT_DIR = saved
