# Stadium Surge: Metro Event Crowd Command (PS-05)

Takes an event's details (venue, attendance, start and end time) and produces:
1. **An ML rush-hour forecast**: predicted footfall per station per hour, with rush hours flagged.
2. **A minute-by-minute crowd plan**: which gates to open, when to activate holding zones, when to add trains.
3. **Announcement scripts** in Gujarati, Hindi and English, with browser text-to-speech.

## Run
```
run.bat            # or manually:
pip install -r requirements.txt
python data/generate_data.py   # synthetic data -> data/*.csv
python train_model.py          # trains model -> model/rush_model.joblib + metrics.json
python app.py                  # http://localhost:5000
```
If the backend is down, the page uses pre-computed results from `static/fallback.js` (header shows "Demo mode").
You can also open `static/index.html` directly. Regenerate the fallback with `python build_fallback.py`.

## How it works
| Layer | File | What it does |
|---|---|---|
| Data | `data/generate_data.py` | 2 years of hourly footfall for 8 Ahmedabad Metro stations (commute peaks, weekends, holidays, growth, seasonality) plus 66 events (IPL/international cricket, concerts, 3 Navratri seasons, riverfront festivals). Event crowds follow arrival curves before the start and exit curves after the end. |
| ML | `core/forecast.py` | `HistGradientBoostingRegressor` with features: station, hour, weekday, month, holiday, event type, metro riders expected at the station, minutes to start, minutes after end. Time-based split (last 3 months held out): R² ≈ 0.92. |
| Planner | `core/planner.py` | 1-minute simulation: arrivals → street queue → gates (90 pax/min each) → paid area (metered at capacity) → trains (1,000 pax). It picks the surge headway, opens gates, activates holding zones and meters the platform, and compares against a no-plan baseline. |
| Announcements | `core/announcements.py` | Templates in Gujarati, Hindi and English, filled with the station, gate, holding zone and minutes. |
| API/UI | `app.py`, `static/` | Flask JSON API and a dashboard built with Chart.js. |

API: `GET /api/meta`, `GET /api/events`, `POST /api/plan`, `GET /api/forecast?station=&date=`, `GET /api/rush-calendar?station=&days=`.

> All data is synthetic, for demonstration only. Station capacities and gate names are illustrative.
