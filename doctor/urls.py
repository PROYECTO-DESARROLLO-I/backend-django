from django.urls import path

from doctor.views import DoctorListView

urlpatterns = [
    path("", DoctorListView.as_view(), name="doctor-list"),
]
