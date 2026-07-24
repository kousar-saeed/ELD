"""
Tests reproducing FMCSA guide worked examples as regression tests.

Reference: FMCSA Driver's Guide to HOS (2022)
  - John Doe completed log example (guide p.18–19)
  - 70-hr/8-day rolling total table (guide p.11)
"""

import unittest
from datetime import datetime

from hos.engine import plan_hos_trip, plan_trip, RouteLeg, _compile_daily_logs, Segment, D, ON, OFF, SB, DutySegment, Stop


class TestPlanTripDirect(unittest.TestCase):
    """Test plan_trip(leg1, leg2, current_cycle_used) returning (list[DutySegment], list[Stop])."""

    def test_plan_trip_with_route_leg_dataclass(self):
        leg1 = RouteLeg(
            distance_miles=180.0,
            duration_hours=3.0,
            start_lat=41.8781,
            start_lng=-87.6298,
            end_lat=39.7684,
            end_lng=-86.1581,
            start_label="Chicago, IL",
            end_label="Indianapolis, IN",
        )
        leg2 = RouteLeg(
            distance_miles=175.0,
            duration_hours=2.8,
            start_lat=39.7684,
            start_lng=-86.1581,
            end_lat=39.9612,
            end_lng=-82.9988,
            start_label="Indianapolis, IN",
            end_label="Columbus, OH",
        )

        segments, stops = plan_trip(leg1, leg2, current_cycle_used=10.0, start_time=datetime(2026, 7, 22, 6, 0))

        self.assertIsInstance(segments, list)
        self.assertIsInstance(stops, list)
        self.assertTrue(all(isinstance(s, DutySegment) for s in segments))
        self.assertTrue(all(isinstance(s, Stop) for s in stops))

        # Check pickup and dropoff stops exist
        pickup_stops = [s for s in stops if s.type == "pickup"]
        dropoff_stops = [s for s in stops if s.type == "dropoff"]
        self.assertEqual(len(pickup_stops), 1)
        self.assertEqual(len(dropoff_stops), 1)


if __name__ == "__main__":
    unittest.main()


class TestJohnDoeExample(unittest.TestCase):
    """
    Reproduce the John Doe worked example from the FMCSA guide (p.18-19).

    John Doe's day (simplified from the guide):
      - 00:00-06:00  Off Duty (6 hrs)
      - 06:00-06:15  Pre-trip inspection, On Duty Not Driving (0.25 hr)
      - 06:15-10:00  Driving (3.75 hrs)
      - 10:00-10:15  Fuel stop, On Duty Not Driving (0.25 hr)
      - 10:15-12:00  Driving (1.75 hrs)
      - 12:00-12:30  Lunch break, Off Duty (0.5 hr)
      - 12:30-17:00  Driving (4.5 hrs)
      - 17:00-17:15  Post-trip, On Duty Not Driving (0.25 hr)
      - 17:15-24:00  Off Duty (6.75 hrs)

    Totals: OFF=13.25, SB=0, D=10.0, ON=0.75 → 24 hrs
    """

    def test_john_doe_daily_totals(self):
        """Daily log totals should sum to 24 hours and match expected breakdown."""
        # Build segments directly — this tests the daily log compiler,
        # which is the component responsible for the log sheet output.
        dt = datetime(2026, 7, 22)
        segments = [
            Segment(OFF, datetime(2026, 7, 22, 0, 0), datetime(2026, 7, 22, 6, 0), "off duty"),
            Segment(ON,  datetime(2026, 7, 22, 6, 0), datetime(2026, 7, 22, 6, 15), "pre-trip"),
            Segment(D,   datetime(2026, 7, 22, 6, 15), datetime(2026, 7, 22, 10, 0), "driving"),
            Segment(ON,  datetime(2026, 7, 22, 10, 0), datetime(2026, 7, 22, 10, 15), "fuel"),
            Segment(D,   datetime(2026, 7, 22, 10, 15), datetime(2026, 7, 22, 12, 0), "driving"),
            Segment(OFF, datetime(2026, 7, 22, 12, 0), datetime(2026, 7, 22, 12, 30), "lunch"),
            Segment(D,   datetime(2026, 7, 22, 12, 30), datetime(2026, 7, 22, 17, 0), "driving"),
            Segment(ON,  datetime(2026, 7, 22, 17, 0), datetime(2026, 7, 22, 17, 15), "post-trip"),
            Segment(OFF, datetime(2026, 7, 22, 17, 15), datetime(2026, 7, 23, 0, 0), "off duty"),
        ]

        logs = _compile_daily_logs(segments)
        self.assertEqual(len(logs), 1, "Should produce exactly 1 daily log")

        totals = logs[0]["totals"]
        # Driving: 3.75 + 1.75 + 4.5 = 10.0
        self.assertAlmostEqual(totals[D], 10.0, places=1)
        # On-Duty: 0.25 + 0.25 + 0.25 = 0.75
        self.assertAlmostEqual(totals[ON], 0.75, places=1)
        # Off-Duty: 6 + 0.5 + 6.75 = 13.25
        self.assertAlmostEqual(totals[OFF], 13.25, places=1)
        # Sleeper: 0
        self.assertAlmostEqual(totals[SB], 0.0, places=1)
        # Must total 24 hrs
        total_hrs = sum(totals.values())
        self.assertAlmostEqual(total_hrs, 24.0, places=1)

    def test_john_doe_segment_count(self):
        """Should produce the correct number of segments in the daily log."""
        segments = [
            Segment(OFF, datetime(2026, 7, 22, 0, 0), datetime(2026, 7, 22, 6, 0)),
            Segment(ON,  datetime(2026, 7, 22, 6, 0), datetime(2026, 7, 22, 6, 15)),
            Segment(D,   datetime(2026, 7, 22, 6, 15), datetime(2026, 7, 22, 10, 0)),
            Segment(ON,  datetime(2026, 7, 22, 10, 0), datetime(2026, 7, 22, 10, 15)),
            Segment(D,   datetime(2026, 7, 22, 10, 15), datetime(2026, 7, 22, 12, 0)),
            Segment(OFF, datetime(2026, 7, 22, 12, 0), datetime(2026, 7, 22, 12, 30)),
            Segment(D,   datetime(2026, 7, 22, 12, 30), datetime(2026, 7, 22, 17, 0)),
            Segment(ON,  datetime(2026, 7, 22, 17, 0), datetime(2026, 7, 22, 17, 15)),
            Segment(OFF, datetime(2026, 7, 22, 17, 15), datetime(2026, 7, 23, 0, 0)),
        ]
        logs = _compile_daily_logs(segments)
        # 9 original segments, all within one day — no gap-fill needed
        self.assertEqual(len(logs[0]["segments"]), 9)


class TestRolling70HrTable(unittest.TestCase):
    """
    Test the 70-hr/8-day cycle enforcement.

    From FMCSA guide p.11: once a driver accumulates 70 hours of on-duty
    time (driving + on-duty not driving) in any 8 consecutive days,
    they must stop until a 34-hr restart is taken.
    """

    def test_cycle_limit_triggers_restart(self):
        """
        If current_cycle_used is 65 and the trip requires ~10 hrs
        of on-duty, a 34-hr restart should be inserted.
        """
        # A trip of 300 miles at ~50mph = 6 hrs driving + 2 hrs on-duty (pickup+dropoff)
        legs = [
            {
                "distance_miles": 150,
                "duration_hours": 3.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Chicago, IL"},
                "end_location": {"lat": 39.77, "lng": -86.16, "label": "Indianapolis, IN"},
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": 150,
                "duration_hours": 3.0,
                "start_location": {"lat": 39.77, "lng": -86.16, "label": "Indianapolis, IN"},
                "end_location": {"lat": 39.96, "lng": -83.00, "label": "Columbus, OH"},
                "type": "drive_to_dropoff",
            },
        ]

        result = plan_hos_trip(
            legs,
            current_cycle_used=65.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )

        # A 34-hr restart warning should be generated
        has_restart_warning = any("34-hr restart" in w for w in result["warnings"])
        self.assertTrue(has_restart_warning, "Should warn about 34-hr restart")

        # A rest stop with type "rest" and label containing "restart" should exist
        restart_stops = [s for s in result["stops"] if "restart" in s.get("label", "")]
        self.assertGreaterEqual(len(restart_stops), 1, "Should have a restart stop")

    def test_accumulation_across_legs(self):
        """Cycle hours should accumulate correctly across multiple legs."""
        # Start with 60 hrs used, trip needs ~12 hrs → should trigger restart
        legs = [
            {
                "distance_miles": 200,
                "duration_hours": 4.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Origin"},
                "end_location": {"lat": 39.77, "lng": -86.16, "label": "Pickup"},
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": 400,
                "duration_hours": 8.0,
                "start_location": {"lat": 39.77, "lng": -86.16, "label": "Pickup"},
                "end_location": {"lat": 39.96, "lng": -83.00, "label": "Dropoff"},
                "type": "drive_to_dropoff",
            },
        ]

        result = plan_hos_trip(
            legs,
            current_cycle_used=60.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )

        has_restart = any("34-hr restart" in w for w in result["warnings"])
        self.assertTrue(has_restart, "Should trigger 34-hr restart when cycle runs out mid-trip")


if __name__ == "__main__":
    unittest.main()
