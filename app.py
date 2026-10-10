"""Stadium Surge - Flask backend.  Run: python app.py  ->  http://localhost:5000"""
import json
import os
from datetime import date, timedelta

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from core.config import EVENT_TYPES, STATIONS, VENUES
from core.forecast import METRICS_PATH, predict_day
from core.planner import generate_plan

ROOT = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="")
TODAY = os.environ.get("DEMO_TODAY", "2026-10-10")


def load_events():
    return pd.read_csv(os.path.join(ROOT, "data", "events.csv"))


def events_on(day):
    ev = load_events()
    return ev[ev.date == day].to_dict("records")


@app.route("/")
def index():
    return send_from_directory(os.path.join(ROOT, "static"), "index.html")


@app.get("/api/meta")
def meta():
    metrics = json.load(open(METRICS_PATH)) if os.path.exists(METRICS_PATH) else None
    return jsonify(today=TODAY, metrics=metrics, event_types=EVENT_TYPES[1:],
                   venues={k: dict(name=v["name"], stations=v["stations"]) for k, v in VENUES.items()},
                   stations={k: dict(name=v["name"], line=v["line"], gates=v["gates"], holding=v["holding"],
                                     hourly_capacity=v["hourly_capacity"], paid_area_capacity=v["paid_area_capacity"])
                             for k, v in STATIONS.items()})


@app.get("/api/events")
def events():
    ev = load_events()
    upcoming = ev[ev.date >= TODAY].head(25)
    past = ev[ev.date < TODAY].tail(15).iloc[::-1]
    return jsonify(upcoming=upcoming.to_dict("records"), past=past.to_dict("records"))


@app.post("/api/plan")
def plan():
    b = request.get_json(force=True)
    p = generate_plan(b.get("name", "Event"), b["event_type"], b["venue"], int(b["expected_attendance"]),
                      b["start_time"], b["end_time"])
    day = b.get("date", TODAY)
    others = [e for e in events_on(day) if e.get("name") != b.get("name")]
    p["forecast"] = predict_day(day, p["summary"]["station"], others + [b])
    return jsonify(p)


@app.get("/api/forecast")
def forecast():
    station, day = request.args.get("station", "MOTERA"), request.args.get("date", TODAY)
    f = predict_day(day, station, events_on(day))
    f["events"] = [e["name"] for e in events_on(day)]
    return jsonify(f)


@app.get("/api/rush-calendar")
def rush_calendar():
    station = request.args.get("station", "MOTERA")
    start = date.fromisoformat(request.args.get("start", TODAY))
    days = min(int(request.args.get("days", 14)), 31)
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        evs = events_on(d)
        f = predict_day(d, station, evs)
        out.append(dict(date=d, events=[e["name"] for e in evs], rush_hours=f["rush_hours"],
                        hours=[dict(label=h["label"], level=h["level"], predicted=h["predicted"]) for h in f["hours"]]))
    return jsonify(station=station, station_name=STATIONS[station]["name"], days=out)


@app.errorhandler(Exception)
def on_error(e):
    return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
