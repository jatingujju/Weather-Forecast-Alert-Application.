from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas import CurrentWeatherResponse, ForecastResponse, HistoryItem
from backend.models import WeatherSnapshot
from backend.services.weather_service import fetch_bundle, bundle_current, bundle_forecast
from backend.services.persistence import save_bundle
from src.providers import WeatherError
import json

router = APIRouter(prefix="/weather", tags=["weather"])

@router.get("/current", response_model=CurrentWeatherResponse)
def current_weather(city: str = Query(..., min_length=1, max_length=120), provider: str = "open-meteo", db: Session = Depends(get_db)):
    try:
        bundle = fetch_bundle(city, provider)
        save_bundle(db, bundle)
        return {"city": bundle.city, "country": bundle.country, "latitude": bundle.lat,
                "longitude": bundle.lon, "source": bundle.source,
                "current": bundle_current(bundle), "notes": bundle.notes}
    except (WeatherError, ValueError) as exc:
        raise HTTPException(status_code=502 if isinstance(exc, WeatherError) else 400, detail=str(exc))

@router.get("/forecast", response_model=ForecastResponse)
def weather_forecast(city: str = Query(..., min_length=1, max_length=120), provider: str = "open-meteo", db: Session = Depends(get_db)):
    try:
        bundle = fetch_bundle(city, provider)
        save_bundle(db, bundle)
        return {"city": bundle.city, "country": bundle.country, "source": bundle.source,
                "forecast": bundle_forecast(bundle), "notes": bundle.notes}
    except (WeatherError, ValueError) as exc:
        raise HTTPException(status_code=502 if isinstance(exc, WeatherError) else 400, detail=str(exc))

@router.get("/history")
def weather_history(city: str = Query(..., min_length=1, max_length=120), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = (db.query(WeatherSnapshot).filter(WeatherSnapshot.city.ilike(city.strip()))
            .order_by(WeatherSnapshot.observed_at.desc()).limit(limit).all())
    return [{"id": r.id, "city": r.city, "country": r.country, "source": r.source,
             "observed_at": r.observed_at.isoformat(), "current": json.loads(r.current_json)} for r in rows]
