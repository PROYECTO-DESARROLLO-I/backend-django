from django.urls import path

from availability.views import (
    AdminDoctorAvailabilityDetailView,
    AdminDoctorAvailabilityView,
    AvailableSlotsView,
    DoctorAvailabilityView,
    ScheduleExceptionDetailView,
    ScheduleExceptionListView,
)

urlpatterns = [
    path("slots/", AvailableSlotsView.as_view(), name="availability-slots"),
    path("doctor/", DoctorAvailabilityView.as_view(), name="doctor-availability"),
    path("manage/", AdminDoctorAvailabilityView.as_view(), name="availability-manage"),
    path(
        "manage/<int:pk>/",
        AdminDoctorAvailabilityDetailView.as_view(),
        name="availability-manage-detail",
    ),
    path("exceptions/", ScheduleExceptionListView.as_view(), name="availability-exceptions"),
    path(
        "exceptions/<int:pk>/",
        ScheduleExceptionDetailView.as_view(),
        name="availability-exceptions-detail",
    ),
]
