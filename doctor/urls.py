from django.urls import path

from doctor.views import DoctorView

urlpatterns = [
    path("", DoctorView.as_view(), name="doctor-list"),
]
