"""Pydantic response contracts for the API."""
from typing import Any
from pydantic import BaseModel, ConfigDict

class HealthResponse(BaseModel):
    status: str
    database: str

class CurrentWeatherResponse(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float
    source: str
    current: dict[str, Any]
    notes: list[str] = []

class ForecastResponse(BaseModel):
    city: str
    country: str
    source: str
    forecast: list[dict[str, Any]]
    notes: list[str] = []

class AlertResponse(BaseModel):
    city: str
    category: str
    severity: str
    title: str
    message: str
    time: str = ""

class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    city: str
    country: str
    source: str
    observed_at: str
    current: dict[str, Any]
