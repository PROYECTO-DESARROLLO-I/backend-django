from django.urls import path

from eps.views import EPSDetailView, EPSListCreateView

urlpatterns = [
    path("", EPSListCreateView.as_view(), name="eps-list"),
    path("<int:pk>/", EPSDetailView.as_view(), name="eps-detail"),
]
