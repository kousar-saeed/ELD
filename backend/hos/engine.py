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

# ── Status codes matching the FMCSA daily-log grid rows ──────────────
OFF = "OFF"   # Off Duty
SB  = "SB"    # Sleeper Berth
D   = "D"     # Driving
ON  = "ON"    # On-Duty (Not Driving)

# Small epsilon to avoid floating-point edge-case loops
_EPS = 1e-9


# =====================================================================
# Data classes
# =====================================================================

class Segment:
    """One contiguous block of a single duty status."""

    __slots__ = ("status", "start", "end", "label")

    def __init__(self, status: str, start: datetime, end: datetime, label: str = ""):
        self.status = status
        self.start = start
        self.end = end
        self.label = label

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "label": self.label,
        }

    def __repr__(self):
        hrs = self.duration_hours
        return f"Segment({self.status}, {hrs:.2f}h, {self.label!r})"


class Stop:
    """A location the driver must stop at during the trip."""

    __slots__ = ("type", "lat", "lng", "label", "arrival_time", "departure_time")

    def __init__(
        self,
        stop_type: str,
        lat: float,
        lng: float,
        label: str,
        arrival_time: datetime,
        departure_time: datetime | None = None,
    ):
        self.type = stop_type
        self.lat = lat
        self.lng = lng
        self.label = label
        self.arrival_time = arrival_time
        self.departure_time = departure_time

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "type": self.type,
            "lat": self.lat,
            "lng": self.lng,
            "label": self.label,
            "arrival_time": self.arrival_time.isoformat(),
        }
        if self.departure_time:
            d["departure_time"] = self.departure_time.isoformat()
        return d


# =====================================================================
# Internal simulation state
# =====================================================================

class _SimState:
    """Mutable HOS clocks carried through the simulation."""

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
        self.segments: list[Segment] = []
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
    def add_segment(self, status: str, hours: float, label: str = "") -> Segment:
        seg = Segment(status, self.now, self.now + timedelta(hours=hours), label)
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
    """Insert a 34-hour restart (cycle limit hit)."""
    state.add_segment(OFF, RESTART_HOURS, "34-hr restart — cycle limit")
    state.drive_today = 0.0
    state.window_elapsed = 0.0
    state.since_break = 0.0
    state.cycle_used = 0.0
    state.warnings.append(
        f"34-hr restart inserted at {state.segments[-1].start.strftime('%Y-%m-%d %H:%M')} — cycle limit reached"
    )


def _insert_10hr_rest(state: _SimState):
    """Insert a 10-hour mandatory off-duty rest."""
    state.add_segment(OFF, REST_HOURS, "10-hr off-duty reset")
    state.drive_today = 0.0
    state.window_elapsed = 0.0
    state.since_break = 0.0
    # cycle_used is NOT reset by a 10-hr rest


def _insert_30min_break(state: _SimState):
    """Insert a 30-minute on-duty break (8-hr driving rule)."""
    state.add_segment(ON, BREAK_DURATION, "30-min break")
    state.since_break = 0.0
    state.window_elapsed += BREAK_DURATION
    state.cycle_used += BREAK_DURATION


def _insert_fuel_stop(state: _SimState, lat: float, lng: float):
    """Insert a 30-minute fuel stop (on-duty not driving)."""
    arrival = state.now
    state.add_segment(ON, FUEL_DURATION, "fuel stop")
    state.window_elapsed += FUEL_DURATION
    state.cycle_used += FUEL_DURATION
    state.distance_since_fuel = 0.0
    state.stops.append(Stop("fuel", lat, lng, "fuel stop", arrival, state.now))


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

    Uses the Haversine approximation on the coordinate deltas to distribute
    the known total distance proportionally, which avoids compound rounding
    errors from per-segment Haversine sums.
    """
    if len(coords) < 2:
        return [0.0]

    # Compute raw segment lengths using simple Euclidean approx on degrees
    # (good enough for proportional distribution along the polyline).
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


# =====================================================================
# Drive simulation
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

    The leg is consumed in chunks; each iteration checks HOS limits in
    the priority order specified in the TRD.
    """
    if distance_miles <= _EPS or duration_hours <= _EPS:
        return

    avg_speed = distance_miles / duration_hours  # mph
    miles_left = distance_miles
    driven_on_leg = 0.0  # miles driven so far on this leg

    while miles_left > _EPS:
        # ── Priority 1: cycle limit ──────────────────────────────────
        if state.cycle_remaining <= _EPS:
            lat, lng = _get_current_pos(
                coords, cum_miles, leg_start_mile + driven_on_leg
            )
            state.stops.append(Stop("rest", lat, lng, "34-hr restart", state.now))
            _insert_34hr_restart(state)
            state.stops[-1].departure_time = state.now

        # ── Priority 2: daily drive / window limit ───────────────────
        if state.drive_remaining <= _EPS or state.window_remaining <= _EPS:
            lat, lng = _get_current_pos(
                coords, cum_miles, leg_start_mile + driven_on_leg
            )
            state.stops.append(Stop("rest", lat, lng, "10-hr off-duty", state.now))
            _insert_10hr_rest(state)
            state.stops[-1].departure_time = state.now

        # ── Priority 3: 30-min break ────────────────────────────────
        if state.break_remaining <= _EPS:
            _insert_30min_break(state)

        # ── Compute the max driveable chunk ──────────────────────────
        max_drive_hrs = min(
            state.drive_remaining,
            state.window_remaining,
            state.break_remaining,
            state.cycle_remaining,
        )
        max_drive_miles = max_drive_hrs * avg_speed

        # ── Priority 4: fuel stop ────────────────────────────────────
        fuel_miles_left = max(0.0, FUEL_INTERVAL_MILES - state.distance_since_fuel)
        if fuel_miles_left < max_drive_miles and fuel_miles_left < miles_left:
            # Drive to the fuel mark first
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
            # Insert fuel stop
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


def _get_current_pos(
    coords: list[list[float]] | None,
    cum_miles: list[float] | None,
    current_mile: float,
) -> tuple[float, float]:
    """Return (lat, lng) at the current mileage, or (0, 0) if no geometry."""
    if coords and cum_miles:
        return _interpolate_coord(coords, cum_miles, current_mile)
    return (0.0, 0.0)


def _on_duty_stop(
    state: _SimState,
    hours: float,
    stop_type: str,
    label: str,
    lat: float,
    lng: float,
):
    """Insert an on-duty (not driving) stop, e.g. pickup / dropoff."""
    remaining = hours

    while remaining > _EPS:
        # Check cycle limit before on-duty time
        if state.cycle_remaining <= _EPS:
            state.stops.append(Stop("rest", lat, lng, "34-hr restart", state.now))
            _insert_34hr_restart(state)
            state.stops[-1].departure_time = state.now

        # Check window limit
        if state.window_remaining <= _EPS:
            state.stops.append(Stop("rest", lat, lng, "10-hr off-duty", state.now))
            _insert_10hr_rest(state)
            state.stops[-1].departure_time = state.now

        chunk = min(remaining, state.window_remaining, state.cycle_remaining)
        if chunk <= _EPS:
            break

        arrival = state.now
        state.add_segment(ON, chunk, label)
        state.window_elapsed += chunk
        state.cycle_used += chunk
        remaining -= chunk

    state.stops.append(Stop(stop_type, lat, lng, label, state.now - timedelta(hours=hours), state.now))


# =====================================================================
# Daily-log compiler
# =====================================================================

def _compile_daily_logs(segments: list[Segment]) -> list[dict]:
    """
    Split a flat list of Segment objects into calendar-day log sheets.

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

def plan_hos_trip(
    legs: list[dict],
    current_cycle_used: float = 0.0,
    start_time: datetime | None = None,
) -> dict:
    """
    Plan an HOS-compliant trip schedule.

    Args:
        legs: list of leg dicts, each with:
            - distance_miles (float)
            - duration_hours (float)
            - start_location: {lat, lng, label}
            - end_location:   {lat, lng, label}
            - geometry: GeoJSON LineString geometry (optional, for coord interpolation)
            - type: "drive_to_pickup" | "drive_to_dropoff"
        current_cycle_used: hours already used in the 70-hr/8-day cycle.
        start_time: trip start datetime (defaults to now).

    Returns:
        dict with keys: stops, daily_logs, warnings
    """
    if start_time is None:
        start_time = datetime.now().replace(second=0, microsecond=0)

    state = _SimState(current_cycle_used, start_time)

    for leg in legs:
        dist = leg["distance_miles"]
        dur = leg["duration_hours"]
        start_loc = leg["start_location"]
        end_loc = leg["end_location"]
        leg_type = leg.get("type", "drive")

        # Extract geometry for coordinate interpolation
        coords = None
        cum_miles = None
        if leg.get("geometry") and leg["geometry"].get("coordinates"):
            coords = leg["geometry"]["coordinates"]
            cum_miles = _build_cumulative_miles(coords, dist)

        # ── Pickup stop: 1 hr on-duty before driving to dropoff ──────
        if leg_type == "drive_to_pickup":
            # Drive to pickup
            _drive_leg(state, dist, dur, coords, dist, 0.0, cum_miles)
            # On-duty at pickup
            _on_duty_stop(
                state, PICKUP_DROPOFF_HOURS, "pickup",
                f"{end_loc['label']} — pickup",
                end_loc["lat"], end_loc["lng"],
            )

        elif leg_type == "drive_to_dropoff":
            # Drive to dropoff
            _drive_leg(state, dist, dur, coords, dist, 0.0, cum_miles)
            # On-duty at dropoff
            _on_duty_stop(
                state, PICKUP_DROPOFF_HOURS, "dropoff",
                f"{end_loc['label']} — dropoff",
                end_loc["lat"], end_loc["lng"],
            )

        else:
            # Generic drive leg
            _drive_leg(state, dist, dur, coords, dist, 0.0, cum_miles)

    return {
        "stops": [s.to_dict() for s in state.stops],
        "daily_logs": _compile_daily_logs(state.segments),
        "warnings": state.warnings,
    }
