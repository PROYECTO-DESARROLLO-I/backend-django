
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
<<<<<<< HEAD
    path("api/patients/", include("patient.urls")),
=======
    path("api/", include("user.urls")),
>>>>>>> feature/login
]
