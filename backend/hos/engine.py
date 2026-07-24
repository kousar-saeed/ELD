"""
Pure-Python HOS (Hours of Service) simulation engine.

Takes route leg data and produces an HOS-compliant schedule with:
  - stops[]   : rest, fuel, pickup, dropoff stop records
  - daily_logs[] : FMCSA-style daily log sheets (segments per calendar day)
  - warnings[] : human-readable notes about inserted restarts, etc.

The engine is stateless and side-effect-free — no I/O, no DB, no network.
All time arithmetic uses Python ``datetime``; distances are in miles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .constants import (
    MAX_DRIVE_HOURS,
    MAX_WINDOW_HOURS,
    BREAK_AFTER_HOURS,
    BREAK_DURATION,
    CYCLE_MAX_HOURS,
    RESTART_HOURS,
    REST_HOURS,
    FUEL_INTERVAL_MILES,
    FUEL_DURATION,
    PICKUP_DROPOFF_HOURS,
)
from .models import DutySegment, Segment, Stop, DailyLog

# ── Status codes matching the FMCSA daily-log grid rows ──────────────
OFF = "OFF"   # Off Duty
SB  = "SB"    # Sleeper Berth
D   = "D"     # Driving
ON  = "ON"    # On-Duty (Not Driving)

# Small epsilon to avoid floating-point edge-case loops
_EPS = 1e-9


# =====================================================================
# Leg input dataclass
# =====================================================================

@dataclass
class RouteLeg:
    """
    One leg of a trip (e.g. current→pickup or pickup→dropoff).

    Attributes:
        distance_miles: total driving distance for this leg.
        duration_hours: estimated driving time for this leg.
        start_lat, start_lng: origin coordinates.
        end_lat, end_lng: destination coordinates.
        start_label, end_label: human-readable location names.
        geometry: optional GeoJSON LineString dict for polyline interpolation.
    """
    distance_miles: float
    duration_hours: float
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    start_label: str = ""
    end_label: str = ""
    geometry: dict | None = None


# =====================================================================
# Internal simulation state
# =====================================================================

class _SimState:
    """
    Mutable HOS clocks carried through the simulation.

    Tracks the five counters specified in TRD §4:
      drive_today, window_elapsed, since_break, cycle_used, distance_since_fuel.
    """

    def __init__(self, current_cycle_used: float, now: datetime):
        self.now = now
        # Per-shift counters (reset after 10-hr off-duty)
        self.drive_today: float = 0.0       # hours driven since last 10-hr rest
        self.window_elapsed: float = 0.0    # hours since 14-hr window opened
        self.since_break: float = 0.0       # driving hrs since last 30-min break
        # Cycle counter (reset after 34-hr restart)
        self.cycle_used: float = current_cycle_used
        # Fuel tracking
        self.distance_since_fuel: float = 0.0
        # Accumulated outputs
        self.segments: list[DutySegment] = []
        self.stops: list[Stop] = []
        self.warnings: list[str] = []

    # ── remaining-capacity helpers ────────────────────────────────────
    @property
    def drive_remaining(self) -> float:
        return max(0.0, MAX_DRIVE_HOURS - self.drive_today)

    @property
    def window_remaining(self) -> float:
        return max(0.0, MAX_WINDOW_HOURS - self.window_elapsed)

    @property
    def break_remaining(self) -> float:
        return max(0.0, BREAK_AFTER_HOURS - self.since_break)

    @property
    def cycle_remaining(self) -> float:
        return max(0.0, CYCLE_MAX_HOURS - self.cycle_used)

    # ── mutation helpers ──────────────────────────────────────────────
    def add_segment(self, status: str, hours: float, label: str = "") -> DutySegment:
        seg = DutySegment(status, self.now, self.now + timedelta(hours=hours), label)
        self.segments.append(seg)
        self.now += timedelta(hours=hours)
        return seg

    def advance(self, hours: float):
        """Advance the clock without creating a segment."""
        self.now += timedelta(hours=hours)


# =====================================================================
# Core simulation helpers
# =====================================================================

def _insert_34hr_restart(state: _SimState):
    """
    Priority 1 action — Insert a 34-hour restart (cycle_used >= 70).

    Resets: drive_today, window_elapsed, since_break, cycle_used (all to 0).
    Ref: TRD §4 rule 1, FMCSA 49 CFR § 395.3(d).
    """
    state.add_segment(OFF, RESTART_HOURS, "34-hr restart — cycle limit")
    state.drive_today = 0.0
    state.window_elapsed = 0.0
    state.since_break = 0.0
    state.cycle_used = 0.0
    state.warnings.append(
        f"34-hr restart inserted at {state.segments[-1].start.strftime('%Y-%m-%d %H:%M')} — cycle limit reached"
    )


def _insert_10hr_rest(state: _SimState):
    """
    Priority 2 action — Insert a 10-hour mandatory off-duty rest
    (drive_today >= 11 OR window_elapsed >= 14).

    Resets: drive_today, window_elapsed, since_break (but NOT cycle_used).
    Ref: TRD §4 rule 2, FMCSA 49 CFR § 395.3(a)(1)-(2).
    """
    state.add_segment(OFF, REST_HOURS, "10-hr off-duty reset")
    state.drive_today = 0.0
    state.window_elapsed = 0.0
    state.since_break = 0.0
    # cycle_used is NOT reset by a 10-hr rest


def _insert_30min_break(state: _SimState):
    """
    Priority 3 action — Insert a 30-minute on-duty break (since_break >= 8).

    Resets: since_break.
    Ref: TRD §4 rule 3, FMCSA 49 CFR § 395.3(a)(3)(ii).
    """
    state.add_segment(ON, BREAK_DURATION, "30-min break")
    state.since_break = 0.0
    state.window_elapsed += BREAK_DURATION
    state.cycle_used += BREAK_DURATION


def _insert_fuel_stop(state: _SimState, lat: float, lng: float):
    """
    Priority 4 action — Insert a 30-minute fuel stop (on-duty not driving).

    Resets: distance_since_fuel.
    Ref: TRD §4 rule 4.
    """
    arrival = state.now
    state.add_segment(ON, FUEL_DURATION, "fuel stop")
    state.window_elapsed += FUEL_DURATION
    state.cycle_used += FUEL_DURATION
    state.distance_since_fuel = 0.0
    state.stops.append(Stop(type="fuel", lat=lat, lng=lng, label="fuel stop",
                            arrival_time=arrival, departure_time=state.now))


# =====================================================================
# Geometry helpers
# =====================================================================

def _interpolate_coord(
    coords: list[list[float]],
    cumulative_miles: list[float],
    target_miles: float,
) -> tuple[float, float]:
    """
    Interpolate a (lat, lng) along a polyline at a given mileage.

    ``coords`` is [[lng, lat], …] (GeoJSON order).
    ``cumulative_miles`` is the running total at each coord index.
    Returns (lat, lng).
    """
    if target_miles <= 0:
        return (coords[0][1], coords[0][0])
    if target_miles >= cumulative_miles[-1]:
        return (coords[-1][1], coords[-1][0])

    for i in range(1, len(cumulative_miles)):
        if cumulative_miles[i] >= target_miles:
            seg_start = cumulative_miles[i - 1]
            seg_end = cumulative_miles[i]
            seg_len = seg_end - seg_start
            if seg_len < _EPS:
                frac = 0.0
            else:
                frac = (target_miles - seg_start) / seg_len
            lng = coords[i - 1][0] + frac * (coords[i][0] - coords[i - 1][0])
            lat = coords[i - 1][1] + frac * (coords[i][1] - coords[i - 1][1])
            return (lat, lng)

    return (coords[-1][1], coords[-1][0])


def _build_cumulative_miles(coords: list[list[float]], total_miles: float) -> list[float]:
    """
    Build a cumulative-distance array for each coordinate point.

    Uses simple Euclidean approx on degree deltas to distribute
    the known total distance proportionally along the polyline.
    """
    if len(coords) < 2:
        return [0.0]

    raw = [0.0]
    for i in range(1, len(coords)):
        dlng = coords[i][0] - coords[i - 1][0]
        dlat = coords[i][1] - coords[i - 1][1]
        raw.append(math.sqrt(dlng * dlng + dlat * dlat))

    raw_total = sum(raw)
    if raw_total < _EPS:
        return [0.0] * len(coords)

    scale = total_miles / raw_total
    cum = [0.0]
    for r in raw[1:]:
        cum.append(cum[-1] + r * scale)
    return cum


def _get_current_pos(
    coords: list[list[float]] | None,
    cum_miles: list[float] | None,
    current_mile: float,
) -> tuple[float, float]:
    """Return (lat, lng) at the current mileage, or (0, 0) if no geometry."""
    if coords and cum_miles:
        return _interpolate_coord(coords, cum_miles, current_mile)
    return (0.0, 0.0)


# =====================================================================
# Drive simulation — TRD §4 drive-loop priority order
# =====================================================================

def _drive_leg(
    state: _SimState,
    distance_miles: float,
    duration_hours: float,
    coords: list[list[float]] | None,
    total_leg_miles: float | None = None,
    leg_start_mile: float = 0.0,
    cum_miles: list[float] | None = None,
):
    """
    Simulate driving a single leg, inserting rests/breaks/fuel as needed.

    The leg is consumed in chunks. Each iteration of the loop checks HOS
    limits in the exact priority order from TRD §4:

        1. cycle_used >= 70     → 34-hr OFF restart, reset drive/window/break/cycle
        2. drive_today >= 11
           OR window_elapsed >= 14 → 10-hr OFF, reset drive/window/break
        3. since_break >= 8     → 30-min ON break, reset since_break
        4. distance_since_fuel + next_chunk >= 1000
                                → drive to 1000-mi mark, 30-min ON fuel stop,
                                  reset distance_since_fuel
        5. Otherwise            → drive the largest chunk allowed by
                                  whichever remaining cap is tightest
    """
    if distance_miles <= _EPS or duration_hours <= _EPS:
        return

    avg_speed = distance_miles / duration_hours  # mph
    miles_left = distance_miles
    driven_on_leg = 0.0  # miles driven so far on this leg

    while miles_left > _EPS:
        # ── Priority 1: cycle_used >= 70 → 34-hr restart ─────────────
        if state.cycle_remaining <= _EPS:
            lat, lng = _get_current_pos(
                coords, cum_miles, leg_start_mile + driven_on_leg
            )
            state.stops.append(Stop(type="rest", lat=lat, lng=lng,
                                    label="34-hr restart", arrival_time=state.now))
            _insert_34hr_restart(state)
            state.stops[-1].departure_time = state.now

        # ── Priority 2: drive_today >= 11 OR window_elapsed >= 14 ────
        if state.drive_remaining <= _EPS or state.window_remaining <= _EPS:
            lat, lng = _get_current_pos(
                coords, cum_miles, leg_start_mile + driven_on_leg
            )
            state.stops.append(Stop(type="rest", lat=lat, lng=lng,
                                    label="10-hr off-duty", arrival_time=state.now))
            _insert_10hr_rest(state)
            state.stops[-1].departure_time = state.now

        # ── Priority 3: since_break >= 8 → 30-min break ─────────────
        if state.break_remaining <= _EPS:
            _insert_30min_break(state)

        # ── Compute the max driveable chunk (tightest remaining cap) ──
        max_drive_hrs = min(
            state.drive_remaining,
            state.window_remaining,
            state.break_remaining,
            state.cycle_remaining,
        )
        max_drive_miles = max_drive_hrs * avg_speed

        # ── Priority 4: fuel stop at 1000-mi mark ────────────────────
        fuel_miles_left = max(0.0, FUEL_INTERVAL_MILES - state.distance_since_fuel)
        if fuel_miles_left < max_drive_miles and fuel_miles_left < miles_left:
            # Drive to the 1000-mi fuel mark first
            if fuel_miles_left > _EPS:
                chunk_hrs = fuel_miles_left / avg_speed
                state.add_segment(D, chunk_hrs, "en route")
                state.drive_today += chunk_hrs
                state.window_elapsed += chunk_hrs
                state.since_break += chunk_hrs
                state.cycle_used += chunk_hrs
                state.distance_since_fuel += fuel_miles_left
                miles_left -= fuel_miles_left
                driven_on_leg += fuel_miles_left
            # Insert 30-min on-duty fuel stop, reset distance_since_fuel
            lat, lng = _get_current_pos(
                coords, cum_miles, leg_start_mile + driven_on_leg
            )
            _insert_fuel_stop(state, lat, lng)
            continue

        # ── Priority 5: drive the largest feasible chunk ─────────────
        chunk_miles = min(max_drive_miles, miles_left)
        if chunk_miles <= _EPS:
            # Safety valve — shouldn't happen if limits are handled above
            break
        chunk_hrs = chunk_miles / avg_speed

        state.add_segment(D, chunk_hrs, "en route")
        state.drive_today += chunk_hrs
        state.window_elapsed += chunk_hrs
        state.since_break += chunk_hrs
        state.cycle_used += chunk_hrs
        state.distance_since_fuel += chunk_miles
        miles_left -= chunk_miles
        driven_on_leg += chunk_miles


def _on_duty_stop(
    state: _SimState,
    hours: float,
    stop_type: str,
    label: str,
    lat: float,
    lng: float,
):
    """
    Insert an on-duty (not driving) stop, e.g. 1-hr pickup / 1-hr dropoff.

    Checks cycle and window limits before each on-duty chunk so that
    a rest is inserted if needed mid-stop.
    """
    remaining = hours

    while remaining > _EPS:
        # Check cycle limit before on-duty time
        if state.cycle_remaining <= _EPS:
            state.stops.append(Stop(type="rest", lat=lat, lng=lng,
                                    label="34-hr restart", arrival_time=state.now))
            _insert_34hr_restart(state)
            state.stops[-1].departure_time = state.now

        # Check window limit
        if state.window_remaining <= _EPS:
            state.stops.append(Stop(type="rest", lat=lat, lng=lng,
                                    label="10-hr off-duty", arrival_time=state.now))
            _insert_10hr_rest(state)
            state.stops[-1].departure_time = state.now

        chunk = min(remaining, state.window_remaining, state.cycle_remaining)
        if chunk <= _EPS:
            break

        state.add_segment(ON, chunk, label)
        state.window_elapsed += chunk
        state.cycle_used += chunk
        remaining -= chunk

    state.stops.append(Stop(type=stop_type, lat=lat, lng=lng, label=label,
                            arrival_time=state.now - timedelta(hours=hours),
                            departure_time=state.now))


# =====================================================================
# Daily-log compiler
# =====================================================================

def _compile_daily_logs(segments: list[DutySegment]) -> list[dict]:
    """
    Split a flat list of DutySegment objects into calendar-day log sheets.

    Each day runs midnight-to-midnight. A segment that spans midnight
    is split across the two days. Returns the list of daily log dicts
    matching the API contract.
    """
    if not segments:
        return []

    # Find the date range
    first_day = segments[0].start.date()
    last_end = segments[-1].end
    if last_end.time() == datetime.min.time() and last_end > segments[0].start:
        last_day = (last_end - timedelta(microseconds=1)).date()
    else:
        last_day = last_end.date()

    daily_logs = []
    current_date = first_day

    while current_date <= last_day:
        day_start = datetime(current_date.year, current_date.month, current_date.day)
        day_end = day_start + timedelta(days=1)

        day_segments = []
        for seg in segments:
            # Skip segments entirely outside this day
            if seg.end <= day_start or seg.start >= day_end:
                continue

            # Clip to this day's boundaries
            clip_start = max(seg.start, day_start)
            clip_end = min(seg.end, day_end)

            if (clip_end - clip_start).total_seconds() < 1:
                continue

            day_segments.append({
                "status": seg.status,
                "start": clip_start.strftime("%H:%M"),
                "end": clip_end.strftime("%H:%M") if clip_end < day_end else "24:00",
                "label": seg.label,
            })

        # Compute totals
        totals = {OFF: 0.0, SB: 0.0, D: 0.0, ON: 0.0}
        for ds in day_segments:
            start_parts = ds["start"].split(":")
            end_parts = ds["end"].split(":")
            start_hr = int(start_parts[0]) + int(start_parts[1]) / 60.0
            end_hr = int(end_parts[0]) + int(end_parts[1]) / 60.0
            totals[ds["status"]] = totals.get(ds["status"], 0.0) + (end_hr - start_hr)

        # Round totals to avoid floating-point noise
        totals = {k: round(v, 2) for k, v in totals.items()}

        # Fill gaps with OFF duty (implicit — the grid starts at midnight)
        if day_segments and day_segments[0]["start"] != "00:00":
            day_segments.insert(0, {
                "status": OFF,
                "start": "00:00",
                "end": day_segments[0]["start"],
                "label": "",
            })
            start_parts = day_segments[0]["end"].split(":")
            gap_hrs = int(start_parts[0]) + int(start_parts[1]) / 60.0
            totals[OFF] = round(totals.get(OFF, 0.0) + gap_hrs, 2)

        last_end = day_segments[-1]["end"] if day_segments else "00:00"
        if last_end != "24:00":
            day_segments.append({
                "status": OFF,
                "start": last_end,
                "end": "24:00",
                "label": "",
            })
            end_parts = last_end.split(":")
            gap_hrs = 24.0 - (int(end_parts[0]) + int(end_parts[1]) / 60.0)
            totals[OFF] = round(totals.get(OFF, 0.0) + gap_hrs, 2)

        daily_logs.append({
            "date": current_date.isoformat(),
            "segments": day_segments,
            "totals": totals,
        })
        current_date += timedelta(days=1)

    return daily_logs


# =====================================================================
# Public API
# =====================================================================

def plan_trip(
    current_to_pickup_leg: RouteLeg | dict,
    pickup_to_dropoff_leg: RouteLeg | dict,
    current_cycle_used: float = 0.0,
    start_time: datetime | None = None,
) -> tuple[list[DutySegment], list[Stop]]:
    """
    Plan an HOS-compliant trip and return (segments, stops).

    Simulation order per TRD §4:
        drive(current→pickup) → on_duty(1hr, pickup)
        → drive(pickup→dropoff) → on_duty(1hr, dropoff)

    Drive-loop priority (checked each iteration, in this order):
        1. cycle_used >= 70        → insert 34-hr OFF, reset drive/window/break/cycle.
        2. drive_today >= 11
           OR window_elapsed >= 14 → insert 10-hr OFF, reset drive/window/break.
        3. since_break >= 8        → insert 30-min ON (break), reset since_break.
        4. distance_since_fuel + next_chunk >= 1000
                                   → drive to 1000-mi mark, insert 30-min ON
                                     (fuel stop), reset distance_since_fuel.
        5. Otherwise               → drive the largest chunk allowed by
                                     whichever remaining cap is tightest.

    Args:
        current_to_pickup_leg: Leg from current location to pickup.
            Either a RouteLeg or a dict with keys: distance_miles,
            duration_hours, start_location {lat, lng, label},
            end_location {lat, lng, label}, and optional geometry.
        pickup_to_dropoff_leg: Leg from pickup to dropoff (same format).
        current_cycle_used: hours already used in the 70-hr/8-day cycle.
        start_time: trip start datetime (defaults to now).

    Returns:
        (segments, stops) — a flat list of DutySegment objects and
        a list of Stop objects placed along the route.
    """
    if start_time is None:
        start_time = datetime.now().replace(second=0, microsecond=0)

    state = _SimState(current_cycle_used, start_time)

    # ── Normalise inputs ─────────────────────────────────────────────
    leg1 = _normalise_leg(current_to_pickup_leg)
    leg2 = _normalise_leg(pickup_to_dropoff_leg)

    # ── Leg 1: drive(current → pickup) ───────────────────────────────
    coords1, cum1 = _extract_geometry(leg1)
    _drive_leg(state, leg1.distance_miles, leg1.duration_hours,
               coords1, leg1.distance_miles, 0.0, cum1)

    # ── 1hr on-duty at pickup ────────────────────────────────────────
    _on_duty_stop(
        state, PICKUP_DROPOFF_HOURS, "pickup",
        f"{leg1.end_label} — pickup",
        leg1.end_lat, leg1.end_lng,
    )

    # ── Leg 2: drive(pickup → dropoff, with fuel stops) ──────────────
    coords2, cum2 = _extract_geometry(leg2)
    _drive_leg(state, leg2.distance_miles, leg2.duration_hours,
               coords2, leg2.distance_miles, 0.0, cum2)

    # ── 1hr on-duty at dropoff ───────────────────────────────────────
    _on_duty_stop(
        state, PICKUP_DROPOFF_HOURS, "dropoff",
        f"{leg2.end_label} — dropoff",
        leg2.end_lat, leg2.end_lng,
    )

    return (state.segments, state.stops)


def _normalise_leg(leg: RouteLeg | dict) -> RouteLeg:
    """Accept either a RouteLeg dataclass or a legacy dict and return a RouteLeg."""
    if isinstance(leg, RouteLeg):
        return leg

    # Legacy dict format (used by plan_hos_trip and tests)
    start_loc = leg.get("start_location", {})
    end_loc = leg.get("end_location", {})
    return RouteLeg(
        distance_miles=leg["distance_miles"],
        duration_hours=leg["duration_hours"],
        start_lat=start_loc.get("lat", 0.0),
        start_lng=start_loc.get("lng", 0.0),
        end_lat=end_loc.get("lat", 0.0),
        end_lng=end_loc.get("lng", 0.0),
        start_label=start_loc.get("label", ""),
        end_label=end_loc.get("label", ""),
        geometry=leg.get("geometry"),
    )


def _extract_geometry(leg: RouteLeg):
    """Extract coordinate array and cumulative miles from a RouteLeg."""
    coords = None
    cum_miles = None
    if leg.geometry and leg.geometry.get("coordinates"):
        coords = leg.geometry["coordinates"]
        cum_miles = _build_cumulative_miles(coords, leg.distance_miles)
    return coords, cum_miles


def plan_hos_trip(
    legs: list[dict],
    current_cycle_used: float = 0.0,
    start_time: datetime | None = None,
) -> dict:
    """
    Plan an HOS-compliant trip schedule (legacy dict-based interface).

    Delegates to ``plan_trip`` for the core simulation, then compiles
    daily logs and returns the full API response dict.

    Args:
        legs: list of leg dicts, each with:
            - distance_miles (float)
            - duration_hours (float)
            - start_location: {lat, lng, label}
            - end_location:   {lat, lng, label}
            - geometry: GeoJSON LineString geometry (optional)
            - type: "drive_to_pickup" | "drive_to_dropoff"
        current_cycle_used: hours already used in the 70-hr/8-day cycle.
        start_time: trip start datetime (defaults to now).

    Returns:
        dict with keys: stops, daily_logs, warnings
    """
    if start_time is None:
        start_time = datetime.now().replace(second=0, microsecond=0)

    # If called with exactly 2 legs in standard pickup→dropoff order,
    # delegate to plan_trip directly.
    if (len(legs) == 2
            and legs[0].get("type") == "drive_to_pickup"
            and legs[1].get("type") == "drive_to_dropoff"):
        state = _SimState(current_cycle_used, start_time)

        leg1 = _normalise_leg(legs[0])
        leg2 = _normalise_leg(legs[1])

        coords1, cum1 = _extract_geometry(leg1)
        _drive_leg(state, leg1.distance_miles, leg1.duration_hours,
                   coords1, leg1.distance_miles, 0.0, cum1)
        _on_duty_stop(
            state, PICKUP_DROPOFF_HOURS, "pickup",
            f"{leg1.end_label} — pickup",
            leg1.end_lat, leg1.end_lng,
        )

        coords2, cum2 = _extract_geometry(leg2)
        _drive_leg(state, leg2.distance_miles, leg2.duration_hours,
                   coords2, leg2.distance_miles, 0.0, cum2)
        _on_duty_stop(
            state, PICKUP_DROPOFF_HOURS, "dropoff",
            f"{leg2.end_label} — dropoff",
            leg2.end_lat, leg2.end_lng,
        )

        return {
            "stops": [s.to_dict() for s in state.stops],
            "daily_logs": _compile_daily_logs(state.segments),
            "warnings": state.warnings,
        }

    # Fallback: generic multi-leg processing
    state = _SimState(current_cycle_used, start_time)

    for leg in legs:
        dist = leg["distance_miles"]
        dur = leg["duration_hours"]
        end_loc = leg.get("end_location", {})
        leg_type = leg.get("type", "drive")
        rl = _normalise_leg(leg)
        coords, cum = _extract_geometry(rl)

        if leg_type == "drive_to_pickup":
            _drive_leg(state, dist, dur, coords, dist, 0.0, cum)
            _on_duty_stop(
                state, PICKUP_DROPOFF_HOURS, "pickup",
                f"{end_loc.get('label', '')} — pickup",
                end_loc.get("lat", 0.0), end_loc.get("lng", 0.0),
            )
        elif leg_type == "drive_to_dropoff":
            _drive_leg(state, dist, dur, coords, dist, 0.0, cum)
            _on_duty_stop(
                state, PICKUP_DROPOFF_HOURS, "dropoff",
                f"{end_loc.get('label', '')} — dropoff",
                end_loc.get("lat", 0.0), end_loc.get("lng", 0.0),
            )
        else:
            _drive_leg(state, dist, dur, coords, dist, 0.0, cum)

    return {
        "stops": [s.to_dict() for s in state.stops],
        "daily_logs": _compile_daily_logs(state.segments),
        "warnings": state.warnings,
    }
