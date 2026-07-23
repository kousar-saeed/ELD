import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import PlanTripRequestSerializer
from routing.ors_client import ORSClient, ORSError
from hos.engine import plan_hos_trip

logger = logging.getLogger(__name__)


class PlanTripView(APIView):
    """
    POST /api/plan-trip/
    Takes current_location, pickup_location, dropoff_location, current_cycle_used
    and returns route geometry, stop schedule, FMCSA daily logs, and warnings.
    """

    def post(self, request):
        serializer = PlanTripRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        current_loc = data['current_location']
        pickup_loc = data['pickup_location']
        dropoff_loc = data['dropoff_location']
        current_cycle_used = data.get('current_cycle_used', 0.0)

        # Initialize ORS client
        try:
            ors_client = ORSClient()
        except ORSError as e:
            logger.error(f"ORSClient init error: {e}")
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 1. Geocode locations
        try:
            current_lat, current_lng = ors_client.geocode(current_loc)
        except ORSError as e:
            return Response(
                {"detail": f"Could not geocode current location '{current_loc}': {e}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            pickup_lat, pickup_lng = ors_client.geocode(pickup_loc)
        except ORSError as e:
            return Response(
                {"detail": f"Could not geocode pickup location '{pickup_loc}': {e}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dropoff_lat, dropoff_lng = ors_client.geocode(dropoff_loc)
        except ORSError as e:
            return Response(
                {"detail": f"Could not geocode dropoff location '{dropoff_loc}': {e}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Get directions for Leg 1 (current -> pickup) and Leg 2 (pickup -> dropoff)
        try:
            leg1_route = ors_client.directions([
                (current_lat, current_lng),
                (pickup_lat, pickup_lng)
            ])
            leg2_route = ors_client.directions([
                (pickup_lat, pickup_lng),
                (dropoff_lat, dropoff_lng)
            ])
        except ORSError as e:
            logger.error(f"ORS directions API error: {e}")
            return Response(
                {"detail": f"Routing API error: {e}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # 3. Combine coordinates and stats for full route response
        leg1_coords = leg1_route['geometry']['coordinates']
        leg2_coords = leg2_route['geometry']['coordinates']
        combined_coords = leg1_coords + leg2_coords[1:] if leg2_coords else leg1_coords

        total_distance = round(leg1_route['distance_miles'] + leg2_route['distance_miles'], 1)
        total_duration = round(leg1_route['duration_hours'] + leg2_route['duration_hours'], 2)

        # 4. Prepare leg objects for HOS engine
        legs_for_engine = [
            {
                "distance_miles": leg1_route['distance_miles'],
                "duration_hours": leg1_route['duration_hours'],
                "start_location": {"lat": current_lat, "lng": current_lng, "label": current_loc},
                "end_location": {"lat": pickup_lat, "lng": pickup_lng, "label": pickup_loc},
                "geometry": leg1_route['geometry'],
                "type": "drive_to_pickup",
            },
            {
                "distance_miles": leg2_route['distance_miles'],
                "duration_hours": leg2_route['duration_hours'],
                "start_location": {"lat": pickup_lat, "lng": pickup_lng, "label": pickup_loc},
                "end_location": {"lat": dropoff_lat, "lng": dropoff_lng, "label": dropoff_loc},
                "geometry": leg2_route['geometry'],
                "type": "drive_to_dropoff",
            },
        ]

        # 5. Run HOS Simulation Engine
        hos_result = plan_hos_trip(legs_for_engine, current_cycle_used=current_cycle_used)

        # 6. Format API response
        return Response({
            "route": {
                "geometry": {
                    "type": "LineString",
                    "coordinates": combined_coords
                },
                "distance_miles": total_distance,
                "duration_hours": total_duration
            },
            "stops": hos_result["stops"],
            "daily_logs": hos_result["daily_logs"],
            "warnings": hos_result["warnings"]
        }, status=status.HTTP_200_OK)
