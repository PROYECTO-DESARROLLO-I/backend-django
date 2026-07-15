from django.urls import path
<<<<<<< HEAD

from headquarters.views import HeadquartersListView

urlpatterns = [
    path("", HeadquartersListView.as_view(), name="headquarters-list"),
]
=======
from .views import HeadquartersListCreateAPIView

urlpatterns = [
    path("", HeadquartersListCreateAPIView.as_view(), name="headquarters-list-create"),
]
>>>>>>> origin/main
