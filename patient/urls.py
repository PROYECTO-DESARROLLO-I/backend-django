from django.urls import path

from .views import (
    PatientActivateView,
    PatientDeactivateView,
    PatientMeView,
    RegisterPatientView,
)

urlpatterns = [
    path("register/", RegisterPatientView.as_view(), name="patient-register"),
    path("me/", PatientMeView.as_view(), name="patient-me"),
    path(
        "<int:pk>/deactivate/",
        PatientDeactivateView.as_view(),
        name="patient-deactivate",
    ),
    path(
        "<int:pk>/activate/",
        PatientActivateView.as_view(),
        name="patient-activate",
    ),
]
