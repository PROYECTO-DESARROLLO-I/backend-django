from django.urls import path

from availability.views import AvailableSlotsView

urlpatterns = [
    path("slots/", AvailableSlotsView.as_view(), name="availability-slots"),
]
