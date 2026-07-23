# TRD — ELD Trip Planner & HOS Log Generator

Companion to PRD.md. Covers architecture, contracts, and the HOS engine spec.

## 1. Architecture

```
React (Vite) ──HTTPS──▶ Django + DRF ──▶ OpenRouteService API (geocode + directions)
   │                         │
   ▼                         ▼
Leaflet map            HOS Engine (pure Python module, no I/O)
+ SVG log sheets        → daily_logs[] + stops[]
```

Stateless request/response. No database in v1 — nothing needs to persist between requests.

## 2. Tech Stack
| Layer | Choice | Why |
|---|---|---|
| Backend | Django + Django REST Framework | required by brief |
| Frontend | React (Vite) | required by brief |
| Routing/geocoding | OpenRouteService (ORS) | free, 2,000 directions req/day, 40/min, has a `driving-hgv` (truck) profile, no card required |
| Map rendering | React-Leaflet + OSM tiles | free, no key |
| Backend host | Render or Railway | Django doesn't fit Vercel's serverless model cleanly |
| Frontend host | Vercel | per brief |

## 3. API Contract

**POST** `/api/plan-trip/`

Request:
```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Indianapolis, IN",
  "dropoff_location": "Columbus, OH",
  "current_cycle_used": 12.5
}
```

Response:
```json
{
  "route": {
    "geometry": { "type": "LineString", "coordinates": [[lng,lat], ...] },
    "distance_miles": 350.2,
    "duration_hours": 6.1
  },
  "stops": [
    { "type": "pickup", "lat": 39.77, "lng": -86.16, "label": "Indianapolis, IN", "arrival_time": "2026-07-22T09:00:00" },
    { "type": "fuel", "lat": 40.1, "lng": -84.9, "label": "~1000mi mark", "arrival_time": "..." },
    { "type": "rest", "lat": 40.3, "lng": -84.2, "label": "10-hr off-duty", "start": "...", "end": "..." },
    { "type": "dropoff", "lat": 39.96, "lng": -83.0, "label": "Columbus, OH", "arrival_time": "..." }
  ],
  "daily_logs": [
    {
      "date": "2026-07-22",
      "segments": [
        { "status": "OFF", "start": "00:00", "end": "06:00", "label": "" },
        { "status": "ON",  "start": "06:00", "end": "07:00", "label": "Indianapolis, IN — pickup" },
        { "status": "D",   "start": "07:00", "end": "14:00", "label": "en route" },
        { "status": "ON",  "start": "14:00", "end": "14:30", "label": "fuel stop" }
      ],
      "totals": { "OFF": 6, "SB": 0, "D": 7, "ON": 1.5 }
    }
  ],
  "warnings": ["34-hr restart inserted on day 2 — cycle limit reached"]
}
```

Error cases: `400` with a message if a location fails to geocode; `502` if ORS is unreachable/rate-limited.

## 4. HOS Engine Spec

Constants:
```
MAX_DRIVE_HOURS       = 11
MAX_WINDOW_HOURS      = 14
BREAK_AFTER_HOURS     = 8      # cumulative driving before 30-min break required
BREAK_DURATION        = 0.5
CYCLE_MAX_HOURS       = 70
RESTART_HOURS         = 34
FUEL_INTERVAL_MILES   = 1000
PICKUP_DROPOFF_HOURS  = 1
```

State tracked per simulation step: `drive_today`, `window_elapsed`, `since_break`, `cycle_used`, `distance_since_fuel`.

Simulation order: `drive(current→pickup)` → `on_duty(1hr, pickup)` → `drive(pickup→dropoff, with fuel stops)` → `on_duty(1hr, dropoff)`.

Drive-loop priority when a limit is hit (check in this order, each iteration):
1. `cycle_used >= 70` → insert 34-hr OFF, reset drive/window/break/cycle.
2. `drive_today >= 11 OR window_elapsed >= 14` → insert 10-hr OFF, reset drive/window/break.
3. `since_break >= 8` → insert 30-min ON (break), reset since_break.
4. `distance_since_fuel + next_chunk >= 1000` → drive to the 1000-mi mark, insert 30-min ON (fuel stop), reset distance_since_fuel.
5. Otherwise, drive the largest chunk allowed by whichever remaining cap is tightest.

**Validation requirement:** unit tests must reproduce the FMCSA guide's own worked examples — the John Doe completed log (guide p.18–19) and the 70-hr/8-day rolling total table (guide p.11) — as regression tests. This is the primary evidence the engine is correct, not just plausible-looking.

Edge cases to explicitly test:
- `current_cycle_used` close to 70 (forces an immediate or early restart)
- Trip short enough to need zero rest stops
- Trip long enough to need 2+ 34-hr restarts
- Distance that lands a fuel stop and a mandatory break at nearly the same point

## 5. Third-Party Integration Details
- ORS endpoints: `/geocode/search` (geocoding), `/v2/directions/driving-hgv/geojson` (routing)
- Rate limits: 2,000 requests/day, 40/min sliding window — plenty for a graded demo, but cache/log responses during dev to avoid burning quota on repeated manual testing
- API key: server-side env var only (`ORS_API_KEY`), never shipped to the frontend
- Fuel/rest stop coordinates: interpolated along the ORS route geometry by cumulative distance, not real gas station lookups

## 6. Backend Structure
```
backend/
  hos/
    engine.py        # pure function(s): trip legs + cycle_used → segments/stops
    constants.py
    tests/
      test_examples.py   # FMCSA guide worked examples
      test_edge_cases.py
  routing/
    ors_client.py     # geocode(), directions()
  api/
    views.py          # /api/plan-trip/
    serializers.py
```

## 7. Frontend Structure
```
frontend/src/
  components/
    TripForm.jsx
    RouteMap.jsx        # Leaflet + polyline + stop markers
    LogSheetStack.jsx    # tabs/carousel across days
    DayLogSVG.jsx        # the actual grid drawing
    LoadingState.jsx
    ErrorState.jsx
  api/client.js
```

## 8. Non-Functional Requirements
- Target response time: <5s per plan request (2 ORS calls + in-memory simulation)
- CORS locked to the deployed frontend origin
- Backend cold-start on free tier: document it in the README rather than let it look like a bug during grading
- No secrets in the frontend bundle

## 9. Milestones (16 hrs / 4 days)
| Day | Hours | Focus |
|---|---|---|
| 1 | ~5 | Scaffold both apps; ORS geocode/directions working standalone; HOS engine built + passing FMCSA-example unit tests |
| 2 | ~4 | DRF endpoint; React form; Leaflet map with route + stop markers |
| 3 | ~4 | SVG log sheet component, multi-day rendering, UI polish |
| 4 | ~3 | Deploy (Vercel + Render), end-to-end smoke test with a multi-restart trip, README, Loom, submit |

## 10. Open Risks (carried from PRD)
- Rolling 8-day window simplification (PRD §7)
- Split sleeper-berth provision not implemented (PRD §7)
- Fuel/rest stop placement is geometric interpolation, not real-world POI lookup
