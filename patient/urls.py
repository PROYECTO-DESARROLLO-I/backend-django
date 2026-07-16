from django.urls import path

from .views import PatientMeView, RegisterPatientView

urlpatterns = [
    path("register/", RegisterPatientView.as_view(), name="patient-register"),
    path("me/", PatientMeView.as_view(), name="patient-me"),
]
