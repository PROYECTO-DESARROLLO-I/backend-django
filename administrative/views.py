from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user.models import User
from user.permissions import IsSuperAdmin

from .models import Administrative
from .serializers import AdministrativeStatusSerializer


def _set_administrative_status(pk, is_active, already_message, request_user=None):
    with transaction.atomic():
        administrative = get_object_or_404(
            Administrative.objects.select_for_update(of=("self", "user")).select_related(
                "user"
            ),
            pk=pk,
        )
        user = administrative.user

        if not is_active:
            if request_user is not None and administrative.user_id == request_user.id:
                return Response(
                    {"detail": "No puedes desactivar tu propia cuenta."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user.rol == User.Role.SUPERADMIN:
                return Response(
                    {
                        "detail": "No se puede desactivar a un superadministrador desde este endpoint."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if user.is_active == is_active:
            return Response(
                {"detail": already_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = is_active
        user.save(update_fields=["is_active", "updated_at"])

        return Response(
            {
                "message": "Administrativo activado correctamente"
                if is_active
                else "Administrativo desactivado correctamente",
                "data": AdministrativeStatusSerializer(administrative).data,
            }
        )


class AdministrativeDeactivateView(APIView):
    """
    POST /api/administratives/<id>/deactivate/ - Desactiva la cuenta del administrativo.
    """

    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        return _set_administrative_status(
            pk,
            is_active=False,
            already_message="El administrativo ya está desactivado.",
            request_user=request.user,
        )


class AdministrativeActivateView(APIView):
    """
    POST /api/administratives/<id>/activate/ - Reactiva la cuenta del administrativo.
    """

    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        return _set_administrative_status(
            pk, is_active=True, already_message="El administrativo ya está activo."
        )
