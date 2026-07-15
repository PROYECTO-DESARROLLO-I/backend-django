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


class IsDoctor(BasePermission):
    """Allows access only to users with the doctor role that have a doctor profile."""

    message = "Solo los médicos pueden realizar esta acción."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol == User.Role.DOCTOR
            and hasattr(request.user, "doctor_profile")
        )


class IsAdministrativeUser(BasePermission):
    """Allows access only to users with superadmin role."""

    message = "Solo el superadministrador puede realizar esta acción."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol in [User.Role.SUPERADMIN,User.Role.ADMINISTRATIVE]
        )

