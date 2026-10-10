"""Pre-compute demo responses into static/fallback.js so the UI works even if the API/model is down."""
import json

from app import app

c = app.test_client()
fb = {
    "meta": c.get("/api/meta").get_json(),
    "events": c.get("/api/events").get_json(),
    "plan": c.post("/api/plan", json=dict(name="India vs New Zealand T20", event_type="cricket", venue="NMS",
                                          date="2026-12-13", expected_attendance=105000,
                                          start_time="19:00", end_time="22:30")).get_json(),
    "forecast": c.get("/api/forecast?station=GUJ_UNI&date=2026-10-17").get_json(),
    "calendar": c.get("/api/rush-calendar?station=GUJ_UNI&days=14").get_json(),
}
with open("static/fallback.js", "w", encoding="utf-8") as f:
    f.write("window.FALLBACK = " + json.dumps(fb, ensure_ascii=False) + ";\n")
print("wrote static/fallback.js", {k: ("error" in v) for k, v in fb.items()})
