"""
OpenRouteService API client for geocoding and HGV route directions.
"""

import os
import requests


class ORSClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('ORS_API_KEY')
        self.base_url = 'https://api.openrouteservice.org'

    def geocode(self, query):
        """Geocode address/city string to [lng, lat]."""
        pass

    def get_directions(self, coordinates):
        """Get driving-hgv GeoJSON route geometry & stats."""
        pass
