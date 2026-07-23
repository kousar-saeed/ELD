from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import PlanTripRequestSerializer


class PlanTripView(APIView):
    def post(self, request):
        serializer = PlanTripRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Trip planning logic will be wired here
        return Response({
            "message": "Plan trip endpoint stub",
            "data": serializer.validated_data
        }, status=status.HTTP_200_OK)
