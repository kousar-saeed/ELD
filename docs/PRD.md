# PRD — ELD Trip Planner & HOS Log Generator

## 1. Overview
A web app that takes a trip (current location, pickup, dropoff, current 70hr/8-day cycle used) and outputs: a route map with required rest/fuel stops, and auto-filled FMCSA-style daily log sheets for the whole trip.

Built for: Full Stack Developer take-home assessment.

## 2. Problem
Property-carrying CMV drivers must stay within FMCSA Hours-of-Service limits (49 CFR Part 395) while planning a trip: 11-hr driving cap, 14-hr on-duty window, mandatory 30-min break after 8 cumulative driving hours, 70-hr/8-day on-duty cap, 34-hr restart. Doing this by hand — and then hand-drawing the log grid — is slow and error-prone. This tool computes the compliant schedule and draws the logs automatically.

## 3. Target User
Dispatchers and drivers planning interstate, property-carrying trips operating under the 70-hr/8-day cycle.

## 4. Goals / What "done" looks like
- Given the 4 inputs, output a route + stop-by-stop schedule that never violates the HOS limits below.
- Output correctly formatted daily log sheet(s) — one per 24-hr period — matching the FMCSA grid layout.
- Live hosted version, works end-to-end for graders with no setup.
- UI/UX is clean enough to read as a real product, not a form-and-JSON-dump.

## 5. Inputs
| Field | Type | Notes |
|---|---|---|
| Current location | text (geocoded) | driver's starting point |
| Pickup location | text (geocoded) | |
| Dropoff location | text (geocoded) | |
| Current Cycle Used | number, 0–70 | hours already burned in the rolling 70-hr/8-day window |

## 6. Outputs

### 6.1 Route Map
- Full route: current → pickup → dropoff
- Markers for pickup, dropoff, every rest stop, every fuel stop
- Total distance and drive time summary

### 6.2 Daily Log Sheets
- One sheet per calendar day touched by the trip
- FMCSA grid format: Off Duty / Sleeper Berth / Driving / On-Duty (Not Driving), midnight–midnight
- Per-status totals, remarks row with location at each status change
- Read-only in v1 (see Non-Goals)

## 7. Governing Assumptions (per assessment brief + simplifications)
- Property-carrying driver, 70-hr/8-day cycle only (60-hr/7-day not modeled).
- No adverse driving conditions exception.
- Fuel stop inserted at least every 1,000 driven miles (~30 min, on-duty not driving).
- 1 hour on-duty (not driving) at pickup, 1 hour at dropoff.
- Trip is assumed to start immediately ("now") — no scheduled future start time.
- **70-hr/8-day cycle is approximated**: `current_cycle_used` is treated as a starting balance that accumulates upward and is only cleared by a full 34-hr restart. True rolling 8-day history isn't available from the given inputs, so exact day-9-drops-off-day-1 accounting isn't modeled.
- **Split sleeper-berth provision (7+2/7+3 pairing) is out of scope for v1** — rest is modeled as simple 10-consecutive-hour off-duty/sleeper resets. Called out explicitly as a known simplification, not an oversight.

## 8. User Stories
- As a dispatcher, I enter a trip and cycle hours and immediately see whether it's HOS-compliant and where the driver needs to stop.
- As a dispatcher, I see the route on a map with every required stop marked, so I can communicate the plan.
- As a driver, I get pre-filled daily logs instead of hand-drawing the grid.

## 9. Non-Goals (v1)
- User accounts / authentication
- Persisting or retrieving past trips
- Manually editing generated logs
- Passenger-carrying vehicle rules
- Adverse driving conditions exception
- Real-time GPS / live tracking
- Team/co-driver scheduling

## 10. UX Requirements
- Single flow: form → loading state → map + log sheets.
- Multi-day trips render as a scrollable/tabbed stack of log sheets, most recent or day 1 first.
- Visual fidelity to the real FMCSA grid: correct row order, color-coded status lines, totals column, remarks.
- Clear error state if a location can't be geocoded (don't fail silently).

## 11. Risks
- Free-tier routing/geocoding API rate limits could affect grading if hit repeatedly in a short window.
- The 8-day rolling window simplification (Section 7) is a known accuracy gap — disclosed up front rather than discovered by the grader.

## 12. Timeline
16 working hours over 4 days. See TRD Section 9 for the milestone breakdown.
