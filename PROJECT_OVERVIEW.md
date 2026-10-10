# Stadium Surge: Project Overview

**Problem statement:** PS-05 · Metro Operations · *The Stadium Surge*

This document explains **what** the project does, **why** it is built this way, and **how** each part works.

---

## 1. WHAT: the problem and what we built

### The problem
Big events (cricket at Narendra Modi Stadium, Navratri garba at GMDC Ground, riverfront festivals) send tens of thousands of people to one or two metro stations within minutes. Operators know the event dates, but they have no ready, step-by-step plan for handling the crowd. Without a plan, people pile up on platforms and staircases, which is a serious crowd-safety risk.

### What we built
A web dashboard for metro operators. It does three things:

| # | Feature | Question it answers |
|---|---------|---------------------|
| 1 | **Rush-hour forecast (ML)** | *When* will the rush come, and at *which hours* and *which stations*? |
| 2 | **Minute-by-minute crowd plan** | *What should we do* each minute: which gates to open, where to hold people, when to add trains? |
| 3 | **Announcement scripts** | *What do we tell passengers?* Ready-made scripts in **Gujarati, Hindi and English**, with audio playback. |

**Input:** event details (name, type, venue, date, expected attendance, start time, end time).
**Output:** a forecast, an action timeline, charts comparing "with plan" and "without plan", and announcements.

---

## 2. WHY: design decisions

| Decision | Reason |
|----------|--------|
| **Add an ML forecast** even though the problem only mentions event days | Knowing the event date isn't enough. Operators need to know the *exact hours* of the rush (e.g. 19:00–20:00 arrivals and 00:00 exits on Navratri) and how it builds over several days (weekend nights are busier). The ML model turns "there is an event" into "this station will be at 73% capacity at 00:00". |
| **A simple, explainable model** (gradient-boosted trees) | It works well on table-style data (hour, weekday, event size), trains in seconds, and we can show which inputs matter most. No deep learning is needed. |
| **A rule-based simulation for the plan** instead of ML | Safety decisions must be explainable and auditable. Rules like "open another gate when arrivals exceed gate capacity" are easy to justify to an operator, and an ML black box isn't. |
| **Compare against a "no plan" baseline** | It shows the plan's impact in numbers (e.g. 12,554 people inside a 2,500-capacity station without a plan, versus 2,500 with one). |
| **Announcements in three languages** | Ahmedabad's passengers are Gujarati, Hindi and English speakers. Pre-written scripts let staff respond instantly instead of improvising. |
| **Synthetic data** | Real station-wise hourly ridership isn't publicly available. We generated realistic data from commute patterns and event crowd behaviour. With real data, the same pipeline can simply be retrained. |
| **Fallback / demo mode** | The dashboard keeps working even if the backend or model fails, by using saved results. That makes the demo reliable. |

---

## 3. HOW: how it works

### 3.1 Architecture

```
        ┌───────────────────────────┐
        │  data/generate_data.py    │  synthetic ridership + event calendar
        └────────────┬──────────────┘
                     ▼
   data/ridership_hourly.csv, events.csv, stations.csv
                     │
                     ▼
        ┌───────────────────────────┐
        │  train_model.py           │  trains ML model -> model/rush_model.joblib
        └────────────┬──────────────┘
                     ▼
┌────────────────────────────────────────────────┐
│ app.py (Flask API)                             │
│   core/forecast.py      -> ML hourly forecast  │
│   core/planner.py       -> minute-by-minute    │
│   core/announcements.py -> GU / HI / EN scripts│
└────────────┬───────────────────────────────────┘
             ▼  JSON
┌────────────────────────────────────────────────┐
│ static/ (index.html + app.js + Chart.js)       │
│   falls back to static/fallback.js if API down │
└────────────────────────────────────────────────┘
```

### 3.2 Data (`data/generate_data.py`)

- **8 stations:** Motera Stadium, Sabarmati, Gujarat University, Old High Court (interchange), Gandhigram, Kalupur, Thaltej, APMC. Each has gates, holding zones, a platform/paid-area capacity and an hourly capacity (`core/config.py`).
- **3 venues**, each mapped to its nearby stations with a share of riders:
  - Narendra Modi Stadium → Motera 75%, Sabarmati 25%
  - GMDC Ground → Gujarat University 80%, Old High Court 20%
  - Riverfront → Gandhigram 55%, Old High Court 45%
- **66 events** (Oct 2024 – Dec 2026): IPL and international cricket, concerts, three Navratri seasons, kite festival, Independence Day, Diwali and New Year events. Past events are marked *completed*, future ones *scheduled*.
- **Hourly ridership** (~112,000 rows) is built from:
  - normal-day patterns: morning and evening commute peaks on weekdays, a flatter curve on weekends
  - holidays, summer and monsoon dips, and ridership growth over time
  - random noise
  - **event surges:**
    - *Metro riders* = attendance × share of attendees who take the metro (cricket 32%, concert 38%, Navratri 22%, riverfront 28%) × the station's share of the venue
    - *Arrival curve:* a bell curve peaking about 60 minutes before the start
    - *Exit curve:* about 10% leave early, the main wave peaks about 20 minutes after the end, and a tail lasts about 2 hours

### 3.3 ML rush-hour forecast (`core/forecast.py`)

- **Model:** `HistGradientBoostingRegressor` (scikit-learn)
- **Target:** passengers per hour at a station
- **Features:**

| Feature | Meaning |
|---------|---------|
| station | which station |
| hour, dow, month | time of day, day of week, month |
| is_weekend, is_holiday | calendar effects |
| event_type | none / cricket / concert / navratri / riverfront |
| event_riders | expected metro riders at this station from the event |
| min_to_start, min_from_end | how far this hour is from the event's start and end |
| in_event | whether the event is in progress during this hour |

- **Validation:** time-based split. It trains on data up to June 2026 and tests on Jul–Oct 2026, which it never saw.
- **Results:** **R² = 0.92**, MAE ≈ 134 passengers/hour overall, ≈ 255 on event hours.
- **Most important features:** minutes after event end, station, minutes to start, hour, event riders. So the model learned that the event's timing drives the rush.
- **Rush levels:** forecast ÷ station hourly capacity

| Level | Load |
|-------|------|
| Low | < 30% |
| Moderate | 30–50% |
| High | 50–80% |
| Critical | ≥ 80% |

- **Safety check:** a prediction is never allowed to fall below the normal-day value, because an event only adds load. If the model file is missing, a simple formula-based forecast is used instead.

### 3.4 Minute-by-minute crowd plan (`core/planner.py`)

The planner simulates the **exit surge** at the main station, one minute at a time, from 45 minutes before the event ends to 150 minutes after:

```
arrivals ─► street queue ─► gates ─► paid area / platform ─► trains
            (holding zones) (90 pax/min    (capped at safe    (1,000 pax per train;
                             per gate)      capacity)          through stations: 2 × 600)
```

**Decisions it makes:**

| Decision | Rule |
|----------|------|
| **Surge headway** | Picks the longest gap between trains (10 → 8 → 6 → 5 → 4 min) whose carrying capacity covers ~85% of the peak 15-minute arrival rate. The minimum is 4 min. It starts 15 minutes before the event ends. |
| **Gates** | Opens enough gates for the next 10 minutes of arrivals (+20% margin). At least 2 gates stay open, and extra gates close as the crowd falls. |
| **Metering** | Lets people in only while the paid area/platform is below capacity, and raises an alert above 85%. |
| **Holding zones** | Activates holding zones one by one as the street queue grows. They are released in reverse order as the queue shrinks. |
| **Shuttle buses** | Requests AMTS/BRTS buses if the worst-case wait is over 25 minutes. |
| **Recovery** | Once fewer than 150 people remain, it restores normal train frequency and stands staff down. |

**Fixed preparation steps** are added around these: deploy staff (1 per 500 riders, plus security) 4 hours before, set gates to exit mode for arriving crowds, open extra ticket counters and promote return QR tickets, and position standby trains 1 hour before the end.

**"No plan" baseline:** normal train frequency, only 2 gates and no metering. It is plotted on the same chart, so the difference is visible.

**Nearby stations:** each secondary station (e.g. Sabarmati for cricket) gets a short advisory with its headway, gate count and holding zone.

**Example: India vs New Zealand T20, 105,000 people, 19:00–22:30**

| Metric | Without plan | With plan |
|--------|-------------|-----------|
| Peak people inside station | 12,554 (capacity 2,500) | 2,500 (capped) |
| Overcrowded minutes | 125 | 0 |
| Station cleared | 150+ min after end | 00:13 (103 min after end) |
| Trains | normal 12-min gap | 4-min gap, +19 trains |

### 3.5 Announcements (`core/announcements.py`)

Six templates, each in Gujarati, Hindi and English, with the station, gate, holding zone and minutes filled in automatically:

1. **Pre-event arrival guidance:** which gate to exit by; buy a return QR ticket now
2. **Gate opening:** a new gate is open, keep moving in a single line
3. **Holding area / batching:** wait in the named zone; next train in N minutes
4. **Extra trains running:** trains every N minutes, please don't rush
5. **Platform crowding:** stay behind the yellow line, let passengers get off first
6. **All clear:** crowd is normal, holding areas closed

Each announcement appears on the timeline at the moment it should be made. The 🔊 **Play** button reads it aloud with the browser's text-to-speech (gu-IN / hi-IN / en-IN voices, if available).

### 3.6 Website (`static/`)

| Tab | What you see |
|-----|--------------|
| **① Event Crowd Plan** | Event form (or pick a scheduled event), 8 key numbers, a minute-by-minute chart (with plan vs. no plan vs. safe capacity), a filterable action timeline, announcement scripts in three languages, nearby-station advice, and the ML hourly forecast for the event day. |
| **② Rush-Hour Forecast (ML)** | Hour-by-hour forecast for any station and date (colored by rush level, against the normal day and capacity), a 14-day rush heatmap, and the upcoming events list with "Plan →" buttons. |
| **③ Model & Data** | How the pipeline works, model accuracy and feature importance. |

The header badge shows **"Live: ML model"** when the backend responds, or **"Demo mode"** when the page is using saved results.

### 3.7 API (`app.py`)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/meta` | Stations, venues, event types, model metrics |
| `GET /api/events` | Upcoming and recent events |
| `POST /api/plan` | Event details in, then the full crowd plan + forecast out |
| `GET /api/forecast?station=&date=` | Hourly forecast for one station and day (uses that day's scheduled events) |
| `GET /api/rush-calendar?station=&days=` | Hourly rush levels for the next N days |

---

## 4. Running it

```
run.bat
```
Or step by step:
```
pip install -r requirements.txt
python data/generate_data.py   # create the data
python train_model.py          # train the model
python app.py                  # open http://localhost:5000
python build_fallback.py       # (optional) refresh the demo-mode results
```

---

## 5. Limitations and next steps

**Limitations (current prototype):**
- The data is **synthetic**. Station capacities, gate names and holding zones are illustrative.
- The simulation treats the station as a single queue. It doesn't model individual staircases or platforms.
- In demo mode, every event shows the same saved plan (the T20 match).

**Next steps:**
- Retrain on real AFC (ticket-gate) data from Ahmedabad Metro.
- Live mode: compare real-time gate counts with the forecast and re-plan when they drift.
- Add weather and ticket sales as model inputs.
- Push announcements to the station PA system and to passengers' phones.
- Coordinate with AMTS/BRTS buses and traffic police.
