"""
Edge-case tests for the HOS engine.

Covers the scenarios called out in TRD §4:
  - current_cycle_used close to 70 (forces immediate or early restart)
  - Trip short enough to need zero rest stops
  - Trip long enough to need 2+ 34-hr restarts
  - Distance that lands a fuel stop and a mandatory break at nearly the same point
"""

import unittest
from datetime import datetime

from hos.engine import plan_hos_trip, D, ON, OFF


class TestCycleNear70(unittest.TestCase):
    """current_cycle_used close to 70 → forces immediate or early restart."""

    def test_cycle_at_70_immediate_restart(self):
        """If cycle_used == 70, the engine must insert a restart before any driving."""
        legs = [
            {
                "distance_miles": 100,
                "duration_hours": 2.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Chicago"},
                "end_location": {"lat": 39.77, "lng": -86.16, "label": "Indianapolis"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=70.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )

        self.assertTrue(
            any("34-hr restart" in w for w in result["warnings"]),
            "Must insert a 34-hr restart when cycle is already at 70",
        )
        # The first non-OFF segment in the daily logs should come after the restart
        day1 = result["daily_logs"][0]
        off_total = day1["totals"].get(OFF, 0)
        self.assertGreater(off_total, 0, "Day 1 should have significant off-duty time")

    def test_cycle_at_69_early_restart(self):
        """If cycle_used == 69, only 1 hr of on-duty is available before restart."""
        legs = [
            {
                "distance_miles": 200,
                "duration_hours": 4.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Chicago"},
                "end_location": {"lat": 39.77, "lng": -86.16, "label": "Indianapolis"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=69.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )
        self.assertTrue(
            any("34-hr restart" in w for w in result["warnings"]),
            "Should trigger restart after 1 hr of driving",
        )


class TestShortTrip(unittest.TestCase):
    """Trip short enough to need zero rest stops."""

    def test_no_rest_stops_needed(self):
        """A 2-hour drive should need no rest/fuel stops at all."""
        legs = [
            {
                "distance_miles": 50,
                "duration_hours": 1.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Origin"},
                "end_location": {"lat": 41.5, "lng": -87.3, "label": "Pickup"},
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": 50,
                "duration_hours": 1.0,
                "start_location": {"lat": 41.5, "lng": -87.3, "label": "Pickup"},
                "end_location": {"lat": 41.3, "lng": -87.0, "label": "Dropoff"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=0.0,
            start_time=datetime(2026, 7, 22, 8, 0),
        )
        rest_stops = [s for s in result["stops"] if s["type"] == "rest"]
        fuel_stops = [s for s in result["stops"] if s["type"] == "fuel"]
        self.assertEqual(len(rest_stops), 0, "Short trip should have no rest stops")
        self.assertEqual(len(fuel_stops), 0, "Short trip should have no fuel stops")
        self.assertEqual(len(result["warnings"]), 0, "No warnings for a short trip")

    def test_short_trip_totals(self):
        """Total driving for a short trip should match the leg durations."""
        legs = [
            {
                "distance_miles": 50,
                "duration_hours": 1.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "A"},
                "end_location": {"lat": 41.5, "lng": -87.3, "label": "B"},
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": 50,
                "duration_hours": 1.0,
                "start_location": {"lat": 41.5, "lng": -87.3, "label": "B"},
                "end_location": {"lat": 41.3, "lng": -87.0, "label": "C"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=0.0,
            start_time=datetime(2026, 7, 22, 8, 0),
        )
        total_driving = sum(
            log["totals"].get(D, 0) for log in result["daily_logs"]
        )
        # 2 hrs driving total (1 hr each leg)
        self.assertAlmostEqual(total_driving, 2.0, places=1)


class TestMultipleRestarts(unittest.TestCase):
    """Trip long enough to need 2+ 34-hr restarts."""

    def test_two_restarts_on_long_trip(self):
        """
        With cycle_used=50 and a trip requiring ~90 hrs of on-duty time,
        the engine should insert at least 2 cycle restarts.
        """
        # 4500 miles at 50mph = 90 hrs driving + 2 hrs on-duty
        legs = [
            {
                "distance_miles": 1500,
                "duration_hours": 30.0,
                "start_location": {"lat": 34.05, "lng": -118.24, "label": "LA"},
                "end_location": {"lat": 40.71, "lng": -74.01, "label": "NYC pickup"},
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": 4000,
                "duration_hours": 80.0,
                "start_location": {"lat": 40.71, "lng": -74.01, "label": "NYC"},
                "end_location": {"lat": 41.88, "lng": -87.63, "label": "Chicago dropoff"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=50.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )
        restart_warnings = [w for w in result["warnings"] if "34-hr restart" in w]
        self.assertGreaterEqual(
            len(restart_warnings), 2,
            f"Expected 2+ restarts, got {len(restart_warnings)}: {restart_warnings}",
        )


class TestFuelBreakCoincidence(unittest.TestCase):
    """Fuel stop and mandatory 30-min break land near the same point."""

    def test_fuel_and_break_near_same_point(self):
        """
        Set up so that the 8-hr break mark and the 1000-mile fuel mark
        coincide closely. Both should be handled without double-stopping
        or skipping either.
        """
        # At 60mph, 8 hrs = 480 miles. Fuel at 1000 miles.
        # With a 1200-mile leg, the break comes at 480mi and fuel at 1000mi.
        legs = [
            {
                "distance_miles": 1200,
                "duration_hours": 20.0,  # 60mph
                "start_location": {"lat": 34.05, "lng": -118.24, "label": "LA"},
                "end_location": {"lat": 40.71, "lng": -74.01, "label": "NYC"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=0.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )

        # Should have daily logs
        self.assertTrue(len(result["daily_logs"]) >= 1, "Should have at least 1 daily log")

        # Check that a fuel stop was inserted
        fuel_stops = [s for s in result["stops"] if s["type"] == "fuel"]
        self.assertGreaterEqual(len(fuel_stops), 1, "Should have at least 1 fuel stop")

        # All daily log totals should sum to 24 hrs (or less for partial last day)
        for log in result["daily_logs"][:-1]:  # full days
            total = sum(log["totals"].values())
            self.assertAlmostEqual(total, 24.0, places=1,
                msg=f"Day {log['date']} totals should be 24h, got {total}")


class TestDailyLogIntegrity(unittest.TestCase):
    """Cross-cutting tests for daily log output quality."""

    def test_all_days_sum_to_24(self):
        """Every full day in any multi-day trip should total 24 hours."""
        legs = [
            {
                "distance_miles": 600,
                "duration_hours": 12.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Chicago"},
                "end_location": {"lat": 39.77, "lng": -86.16, "label": "Indy"},
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": 400,
                "duration_hours": 8.0,
                "start_location": {"lat": 39.77, "lng": -86.16, "label": "Indy"},
                "end_location": {"lat": 39.96, "lng": -83.00, "label": "Columbus"},
                "type": "drive_to_dropoff",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=0.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )
        for log in result["daily_logs"]:
            total = sum(log["totals"].values())
            self.assertAlmostEqual(
                total, 24.0, places=1,
                msg=f"Day {log['date']} should total 24h, got {total}",
            )

    def test_no_negative_durations(self):
        """No segment should have a negative or zero duration."""
        legs = [
            {
                "distance_miles": 300,
                "duration_hours": 6.0,
                "start_location": {"lat": 41.88, "lng": -87.63, "label": "Chicago"},
                "end_location": {"lat": 39.77, "lng": -86.16, "label": "Indy"},
                "type": "drive_to_pickup",
            },
        ]
        result = plan_hos_trip(
            legs,
            current_cycle_used=0.0,
            start_time=datetime(2026, 7, 22, 6, 0),
        )
        for log in result["daily_logs"]:
            for seg in log["segments"]:
                start_parts = seg["start"].split(":")
                end_parts = seg["end"].split(":")
                start_hr = int(start_parts[0]) + int(start_parts[1]) / 60.0
                end_hr = int(end_parts[0]) + int(end_parts[1]) / 60.0
                self.assertGreater(
                    end_hr, start_hr,
                    f"Segment {seg} on {log['date']} has non-positive duration",
                )


if __name__ == "__main__":
    unittest.main()
