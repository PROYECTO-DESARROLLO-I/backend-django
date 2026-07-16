from rest_framework.permissions import BasePermission

from user.models import User


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
    """Allows access only to users with administrative or superadmin role."""

    message = "Solo el personal administrativo o el superadministrador pueden realizar esta acción."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol in _ADMIN_ROLES
        )


class IsSuperAdmin(BasePermission):
    """Allows access only to users with superadmin role."""

    message = "Solo el superadministrador puede gestionar las restricciones del negocio."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol == User.Role.SUPERADMIN
        )
