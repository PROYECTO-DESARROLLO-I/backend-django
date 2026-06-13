
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("user.urls")),
    path("api/specialties/", include("specialties.urls")),
    path("api/doctors/", include("doctor.urls")),
    path("api/availability/", include("availability.urls")),
    path("api/appointments/", include("appointment.urls")),
]
