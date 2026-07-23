"""
URL configuration for eld_planner project.
"""
from django.contrib import admin
from django.urls import path
from api.views import PlanTripView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/plan-trip/', PlanTripView.as_view(), name='plan-trip'),
]
