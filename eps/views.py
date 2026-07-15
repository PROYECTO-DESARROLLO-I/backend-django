from rest_framework import generics
from rest_framework.permissions import AllowAny

from eps.models import EPS
from eps.serializers import EPSSerializer
from user.models import User
from user.permissions import IsSuperAdmin


class EPSListCreateView(generics.ListCreateAPIView):
    serializer_class = EPSSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsSuperAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated and user.rol == User.Role.SUPERADMIN:
            return EPS.objects.all()
        return EPS.objects.filter(active=True)


class EPSDetailView(generics.RetrieveUpdateDestroyAPIView):
    # Only the superadmin manages individual EPS records (create/update/delete and the
    # detail view); the public dropdown only needs the list endpoint above.
    queryset = EPS.objects.all()
    serializer_class = EPSSerializer
    permission_classes = [IsSuperAdmin]
