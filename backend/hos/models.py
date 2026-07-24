"""
Data models for the HOS (Hours of Service) engine.
Plain Python dataclasses — zero I/O, zero Django ORM.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, Any


DutyStatus = Literal["OFF", "SB", "D", "ON"]
StopType = Literal["pickup", "dropoff", "rest", "fuel", "break"]


@dataclass
class DutySegment:
    """One contiguous block of a single duty status (OFF, SB, D, ON)."""
    status: DutyStatus
    start: datetime
    end: datetime
    label: str = ""

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "label": self.label,
        }


# Alias for backward-compatibility
Segment = DutySegment


@dataclass
class Stop:
    """A location the driver must stop at during the trip (pickup, dropoff, rest, fuel, break)."""
    type: StopType
    lat: float
    lng: float
    label: str
    arrival_time: datetime
    departure_time: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
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


@dataclass
class DailyLog:
    """FMCSA daily log sheet representation for a single calendar day."""
    date: str
    segments: list[DutySegment] = field(default_factory=list)
    totals: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "segments": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.segments],
            "totals": self.totals,
        }
