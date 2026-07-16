from django.urls import path

from appointment.views import (
    AppointmentCreateView,
    AppointmentDetailView,
    AppointmentListView,
    AppointmentRescheduleView,
    AppointmentPatientRescheduleView,
    DoctorAppointmentListView,
    AppointmentCancelView,
    AppointmentDoctorCancelView,
)
from appointment.views import AppointmentCreateView, AppointmentDetailView, AppointmentListView, PatientSearchView

urlpatterns = [
    path("", AppointmentListView.as_view(), name="appointment-list"),
    path("book/", AppointmentCreateView.as_view(), name="appointment-create"),
    path("doctor/", DoctorAppointmentListView.as_view(), name="doctor-appointment-list"),
    path("<int:pk>/", AppointmentDetailView.as_view(), name="appointment-detail"),
    path("<int:pk>/reschedule/", AppointmentRescheduleView.as_view(), name="appointment-reschedule"),
    path('<int:pk>/patient-reschedule/', AppointmentPatientRescheduleView.as_view(), name='appointment-patient-reschedule'),
    path('patients/search/', PatientSearchView.as_view(), name='patient-search'),
    path('<int:pk>/cancel/',     AppointmentCancelView.as_view(), name='appointment-cancel'),
    path('<int:pk>/doctor-cancel/', AppointmentDoctorCancelView.as_view(), name='appointment-doctor-cancel'),

]
