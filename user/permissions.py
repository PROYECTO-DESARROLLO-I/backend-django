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


_ADMIN_ROLES = {User.Role.ADMINISTRATIVE, User.Role.SUPERADMIN}


class IsAdministrative(BasePermission):
    """Allows access only to users with administrative or superadmin role."""

    message = "Solo el personal administrativo puede realizar esta acción."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol in _ADMIN_ROLES
        )

