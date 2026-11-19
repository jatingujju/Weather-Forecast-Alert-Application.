# FastAPI + SQLite Backend Setup

This is an additive backend layer. It keeps the existing `src/`, `main.py`, and `app_streamlit.py` intact.

## 1. Install backend dependencies

Run from the project root after activating `.venv`:

```powershell
python -m pip install "fastapi>=0.110" "uvicorn[standard]>=0.27" "sqlalchemy>=2.0" "pydantic>=2.0"
```

## 2. Start the API

```powershell
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## 3. Try the endpoints

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/weather/current?city=Pune
GET http://127.0.0.1:8000/weather/forecast?city=Pune
GET http://127.0.0.1:8000/alerts?city=Pune
GET http://127.0.0.1:8000/weather/history?city=Pune
GET http://127.0.0.1:8000/alerts/history?city=Pune
```

Open-Meteo is the default and does not require an API key. For OpenWeatherMap, create `.env` from `.env.example`, set `OPENWEATHER_API_KEY`, and pass `&provider=openweathermap`.

The SQLite database is created automatically at `data/weather_app.db`. Do not commit the database file to GitHub; add `data/*.db` to `.gitignore` if it is not already excluded.

## Notes

- API endpoints call the existing provider and alert modules; no parallel alert implementation is introduced.
- `weather/history` returns records fetched through this API after the database was introduced. It cannot reconstruct older CSV/JSON reports automatically.
- AQI is not currently returned by the existing provider module, so AQI endpoints/alerts are not claimed as implemented.
- Current weather and forecast endpoints make a live provider request each time; scheduled refresh/caching is a later phase.
