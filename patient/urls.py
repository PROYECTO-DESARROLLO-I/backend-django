from django.urls import path

from .views import RegisterPatientView

urlpatterns = [
    path("register/", RegisterPatientView.as_view(), name="patient-register"),
]
