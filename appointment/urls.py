from django.urls import path

from appointment.views import (
    AppointmentCreateView,
    AppointmentDetailView,
    AppointmentListView,
    AppointmentRescheduleView,
    DoctorAppointmentListView,
    AppointmentCancelView,
)
from appointment.views import AppointmentCreateView, AppointmentDetailView, AppointmentListView, PatientSearchView

urlpatterns = [
    path("", AppointmentListView.as_view(), name="appointment-list"),
    path("book/", AppointmentCreateView.as_view(), name="appointment-create"),
    path("doctor/", DoctorAppointmentListView.as_view(), name="doctor-appointment-list"),
    path("<int:pk>/", AppointmentDetailView.as_view(), name="appointment-detail"),
    path("<int:pk>/reschedule/", AppointmentRescheduleView.as_view(), name="appointment-reschedule"),
    path('patients/search/', PatientSearchView.as_view(), name='patient-search'),
    path('<int:pk>/cancel/',     AppointmentCancelView.as_view(), name='appointment-cancel'),
    
]
