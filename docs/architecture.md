# Architecture

```
 user input: city name(s), mode, thresholds, (API key in .env)
        |
        v
 +------------------+   +-------------------+   +----------------------+
 | simulator.py     |   | providers.py      |   | providers.py         |
 | fake data, no    |   | Open-Meteo        |   | OpenWeatherMap       |
 | internet needed  |   | (no key)          |   | (key from .env)      |
 +--------+---------+   +---------+---------+   +----------+-----------+
          \                       |                        /
           +----------------------+-----------------------+
                                  v
                    WeatherBundle  (models.py)
                    same columns + same units for every source
                    (deg C, m/s, mm, %), local city time
                                  |
                +-----------------+------------------+
                v                                    v
       alerts.py (rule engine)               analysis.py
       time-window rules ->                  current table, daily summary,
       Alert objects                         48 h facts, alert matrix
                |                                    |
                +----------------+-------------------+
                                 v
          +----------------+  +------------------+  +----------------+
          | report.py      |  | visualize.py     |  | notify.py      |
          | CSV, JSON,     |  | PNG charts       |  | optional email |
          | text report    |  | (Matplotlib)     |  | (dry run by    |
          +----------------+  +------------------+  |  default)      |
                                                    +----------------+
 main.py = command line.  app_streamlit.py = optional dashboard.
```

## Why a common format (WeatherBundle)?

Each weather service names and measures things differently. Converting
everything once, at the edge, means the alert rules and charts never need to
know where the data came from, and a new provider only needs one new parser.

## Alert rules (all thresholds are in `src/config.py`)

| Alert        | Looks at              | Warning              | Critical                  |
|--------------|-----------------------|----------------------|---------------------------|
| Heat         | next 48 h, max temp   | >= 37 C              | >= 40 C                   |
| Rain         | next 12 h chance      | chance >= 60 %       | >= 50 mm in next 24 h     |
| Wind gusts   | next 24 h             | >= 15 m/s (54 km/h)  | >= 20 m/s (72 km/h)       |
| Thunderstorm | next 24 h             | any storm            | 3 h or more of storm      |
| Humidity     | next 12 h average     | info: >= 85 %        | -                         |
| UV index     | rest of today         | >= 8                 | >= 11                     |

Rules use real time windows (not "the first 12 rows"), so they behave the
same for 1-hour data (Open-Meteo) and 3-hour data (OpenWeatherMap).

## Safety and robustness choices

- API keys live only in `.env` (ignored by Git) and are never printed.
- Network and API problems become friendly messages (`WeatherError`).
- Missing values (for example UV from OpenWeatherMap) skip that rule instead of crashing.
- Timestamps are sorted and de-duplicated; times stay in the city's local time.
- Email is a dry run unless SMTP settings exist, and the same alert is not sent twice within 12 hours.
