from django.urls import path
from .views import HeadquartersListCreateAPIView

urlpatterns = [
    path("", HeadquartersListCreateAPIView.as_view(), name="headquarters-list-create"),
]