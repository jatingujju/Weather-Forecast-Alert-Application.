"""Save weather snapshots and evaluated alerts to SQLite."""
import json
from datetime import timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import WeatherSnapshot, AlertRecord
from backend.services.weather_service import bundle_current, bundle_forecast


def save_bundle(db: Session, bundle):
    observed = bundle.now.to_pydatetime()
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    current = bundle_current(bundle)
    forecast = bundle_forecast(bundle)
    stmt = select(WeatherSnapshot).where(
        WeatherSnapshot.city == bundle.city,
        WeatherSnapshot.source == bundle.source,
        WeatherSnapshot.observed_at == observed,
    )
    record = db.scalar(stmt)
    if record is None:
        record = WeatherSnapshot(city=bundle.city, country=bundle.country,
            latitude=float(bundle.lat), longitude=float(bundle.lon), source=bundle.source,
            observed_at=observed, current_json=json.dumps(current), forecast_json=json.dumps(forecast))
        db.add(record)
    else:
        record.current_json = json.dumps(current)
        record.forecast_json = json.dumps(forecast)
    db.commit()
    db.refresh(record)
    return record


def save_alerts(db: Session, bundle, alerts):
    # Each evaluation is recorded as an audit snapshot; repeated API calls are visible.
    rows = [AlertRecord(city=a.city, category=a.category, severity=a.severity,
        title=a.title, message=a.message,
        alert_time="" if a.time is None else str(a.time), source=bundle.source) for a in alerts]
    if rows:
        db.add_all(rows)
        db.commit()
    return rows
