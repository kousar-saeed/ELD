#!/usr/bin/env python3
"""
Throwaway smoke-test: geocodes two cities and prints the route distance.

Usage:
    ORS_API_KEY=<your-key> python test_ors.py

Run from the backend/ directory.
"""

import os
import sys

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Make sure our package is importable
sys.path.insert(0, os.path.dirname(__file__))

from routing.ors_client import ORSClient, ORSError


def main():
    try:
        client = ORSClient()
    except ORSError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("=== ORS Smoke Test ===\n")

    # --- Geocode ---
    origin = "Chicago, IL"
    destination = "Indianapolis, IN"

    print(f"Geocoding '{origin}' ...")
    lat1, lng1 = client.geocode(origin)
    print(f"  -> ({lat1:.5f}, {lng1:.5f})")

    print(f"Geocoding '{destination}' ...")
    lat2, lng2 = client.geocode(destination)
    print(f"  -> ({lat2:.5f}, {lng2:.5f})")

    # --- Directions ---
    print(f"\nFetching driving-hgv route: {origin} → {destination} ...")
    route = client.directions([(lat1, lng1), (lat2, lng2)])

    print(f"  Distance : {route['distance_miles']:.1f} miles")
    print(f"  Duration : {route['duration_hours']:.2f} hours")
    print(f"  Geometry : LineString with {len(route['geometry']['coordinates'])} points")

    print("\n✅ ORS integration working!")


if __name__ == '__main__':
    main()
