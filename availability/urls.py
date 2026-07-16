from django.urls import path

from availability.views import AvailableSlotsView, DoctorAvailabilityView

urlpatterns = [
    path("slots/", AvailableSlotsView.as_view(), name="availability-slots"),
    path("doctor/", DoctorAvailabilityView.as_view(), name="doctor-availability"),
]
