from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from rest_framework import status


class PlanTripAPITest(TestCase):
    def setUp(self):
        self.url = reverse('plan-trip')
        self.valid_payload = {
            "current_location": "Chicago, IL",
            "pickup_location": "Indianapolis, IN",
            "dropoff_location": "Columbus, OH",
            "current_cycle_used": 10.0
        }

    def test_missing_fields_returns_400(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.views.ORSClient')
    def test_successful_plan_trip(self, MockORSClient):
        # Configure mock ORS client
        mock_instance = MockORSClient.return_value
        mock_instance.geocode.side_effect = [
            (41.8781, -87.6298),  # Chicago
            (39.7684, -86.1581),  # Indianapolis
            (39.9612, -82.9988),  # Columbus
        ]
        mock_instance.directions.side_effect = [
            {
                "geometry": {"type": "LineString", "coordinates": [[-87.6298, 41.8781], [-86.1581, 39.7684]]},
                "distance_miles": 180.0,
                "duration_hours": 3.0
            },
            {
                "geometry": {"type": "LineString", "coordinates": [[-86.1581, 39.7684], [-82.9988, 39.9612]]},
                "distance_miles": 175.0,
                "duration_hours": 2.8
            }
        ]

        response = self.client.post(self.url, self.valid_payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("route", data)
        self.assertIn("stops", data)
        self.assertIn("daily_logs", data)
        self.assertIn("warnings", data)
        self.assertEqual(data["route"]["distance_miles"], 355.0)

    @patch('api.views.ORSClient')
    def test_geocoding_failure_returns_400(self, MockORSClient):
        from routing.ors_client import ORSError
        mock_instance = MockORSClient.return_value
        mock_instance.geocode.side_effect = ORSError("Location not found")

        response = self.client.post(self.url, self.valid_payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Could not geocode", response.json()["detail"])
