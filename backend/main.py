"""FastAPI application entry point."""
from fastapi import FastAPI
from backend.database import Base, engine
from backend import models  # noqa: F401 - registers ORM tables
from backend.routers import weather, alerts

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Weather Forecast & Alert API", version="1.0.0",
              description="Weather data, forecasts, persistent history and risk alerts.")
app.include_router(weather.router)
app.include_router(alerts.router)

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "database": "sqlite"}

@app.get("/", tags=["system"])
def root():
    return {"message": "Weather Forecast & Alert API", "docs": "/docs", "health": "/health"}
