from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import AlertRecord
from backend.services.weather_service import fetch_bundle
from backend.services.persistence import save_bundle, save_alerts
from src.alerts import evaluate
from src.providers import WeatherError

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("")
def get_alerts(city: str = Query(..., min_length=1, max_length=120), provider: str = "open-meteo", db: Session = Depends(get_db)):
    try:
        bundle = fetch_bundle(city, provider)
        save_bundle(db, bundle)
        alerts = evaluate(bundle)
        save_alerts(db, bundle, alerts)
        return {"city": bundle.city, "source": bundle.source, "count": len(alerts),
                "alerts": [a.to_dict() for a in alerts]}
    except (WeatherError, ValueError) as exc:
        raise HTTPException(status_code=502 if isinstance(exc, WeatherError) else 400, detail=str(exc))

@router.get("/history")
def alert_history(city: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(AlertRecord)
    if city:
        query = query.filter(AlertRecord.city.ilike(city.strip()))
    rows = query.order_by(AlertRecord.evaluated_at.desc()).limit(limit).all()
    return [{"id": r.id, "city": r.city, "category": r.category, "severity": r.severity,
             "title": r.title, "message": r.message, "time": r.alert_time,
             "source": r.source, "evaluated_at": r.evaluated_at.isoformat()} for r in rows]
