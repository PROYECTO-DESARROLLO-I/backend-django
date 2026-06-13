from django.urls import path

from appointment.views import AppointmentCreateView, AppointmentDetailView, AppointmentListView

urlpatterns = [
    path("", AppointmentListView.as_view(), name="appointment-list"),
    path("book/", AppointmentCreateView.as_view(), name="appointment-create"),
    path("<int:pk>/", AppointmentDetailView.as_view(), name="appointment-detail"),
]
