from django.urls import path

from headquarters.views import HeadquartersListView

urlpatterns = [
    path("", HeadquartersListView.as_view(), name="headquarters-list"),
]
