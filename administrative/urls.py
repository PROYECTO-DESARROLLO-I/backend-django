from django.urls import path

from .views import AdministrativeActivateView, AdministrativeDeactivateView

urlpatterns = [
    path(
        "<int:pk>/deactivate/",
        AdministrativeDeactivateView.as_view(),
        name="administrative-deactivate",
    ),
    path(
        "<int:pk>/activate/",
        AdministrativeActivateView.as_view(),
        name="administrative-activate",
    ),
]
