
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/patients/", include("patient.urls")),
    path("api/auth/", include("user.urls")),
    path("api/specialties/", include("specialties.urls")),
    path("api/doctors/", include("doctor.urls")),
    path("api/availability/", include("availability.urls")),
    path("api/appointments/", include("appointment.urls")),
    path("api/headquarters/", include("headquarters.urls")),
    path("api/rules/", include("rules.urls")),
    path("api/eps/", include("eps.urls")),
    path("api/dashboard/", include("dashboard.urls")),
]
