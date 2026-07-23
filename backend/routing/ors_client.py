"""
OpenRouteService API client for geocoding and HGV route directions.

Reads API key from the ORS_API_KEY environment variable.
ORS docs: https://openrouteservice.org/dev/#/api-docs
"""

import os
import requests


# Metres-to-miles conversion factor
_METRES_PER_MILE = 1_609.344


class ORSError(Exception):
    """Raised when an ORS API call fails."""
    pass


class ORSClient:
    """Thin wrapper around the OpenRouteService REST API."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('ORS_API_KEY')
        if not self.api_key:
            raise ORSError(
                'ORS_API_KEY is not set. '
                'Provide it as an env var or pass api_key= to ORSClient().'
            )
        self.base_url = 'https://api.openrouteservice.org'
        self._headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json, application/geo+json',
        }

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------
    def geocode(self, location: str) -> tuple[float, float]:
        """
        Geocode a free-text location string.

        Returns:
            (lat, lng) tuple of floats.

        Raises:
            ORSError: if the location cannot be geocoded or the API errors.
        """
        url = f'{self.base_url}/geocode/search'
        params = {
            'api_key': self.api_key,
            'text': location,
            'size': 1,
        }

        resp = requests.get(url, params=params, timeout=15)

        if resp.status_code != 200:
            raise ORSError(
                f'Geocode request failed ({resp.status_code}): {resp.text}'
            )

        data = resp.json()
        features = data.get('features', [])
        if not features:
            raise ORSError(f'No geocoding results for "{location}"')

        # ORS returns [lng, lat]; we expose (lat, lng) — more intuitive
        coords = features[0]['geometry']['coordinates']
        lng, lat = coords[0], coords[1]
        return (lat, lng)

    # ------------------------------------------------------------------
    # Directions
    # ------------------------------------------------------------------
    def directions(
        self,
        coords: list[tuple[float, float]],
        profile: str = 'driving-hgv',
    ) -> dict:
        """
        Get a route between two or more waypoints.

        Args:
            coords: list of (lat, lng) tuples in travel order.
            profile: ORS routing profile (default ``driving-hgv``).

        Returns:
            dict with keys:
                geometry  – GeoJSON LineString dict  (coordinates are [lng, lat])
                distance_miles – total route distance in miles (float)
                duration_hours – total estimated travel time in hours (float)

        Raises:
            ORSError: on API failure.
        """
        url = f'{self.base_url}/v2/directions/{profile}/geojson'

        # ORS expects [[lng, lat], …]
        body = {
            'coordinates': [[lng, lat] for lat, lng in coords],
        }

        resp = requests.post(url, json=body, headers=self._headers, timeout=30)

        if resp.status_code != 200:
            raise ORSError(
                f'Directions request failed ({resp.status_code}): {resp.text}'
            )

        data = resp.json()
        feature = data['features'][0]
        summary = feature['properties']['summary']

        return {
            'geometry': feature['geometry'],                       # GeoJSON LineString
            'distance_miles': summary['distance'] / _METRES_PER_MILE,
            'duration_hours': summary['duration'] / 3600.0,
        }
