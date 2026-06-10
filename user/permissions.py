from rest_framework.permissions import BasePermission

from user.models import User


class IsAdministrativeUser(BasePermission):
    message = "Solo usuarios con rol Administrativo pueden acceder a esta funcionalidad."

    def has_permission(self, request, view):
        return (
            bool(request.user and request.user.is_authenticated)
            and request.user.is_active
            and request.user.rol == User.Role.ADMINISTRATIVE
        )
