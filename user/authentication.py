from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


def get_user_clinic_context(user):
    context = {
        "headquarters": [],
        "profile": None,
    }

    if hasattr(user, "administrative_profile"):
        administrative = user.administrative_profile
        context["profile"] = "administrativo"
        if administrative.headquarters_id:
            context["headquarters"].append(
                {
                    "id": administrative.headquarters_id,
                    "name": administrative.headquarters.name,
                }
            )

    if hasattr(user, "doctor_profile"):
        doctor = user.doctor_profile
        context["profile"] = "medico"
        headquarters = {}
        for availability in doctor.availabilities.select_related("headquarters").filter(
            active=True,
            headquarters__isnull=False,
            headquarters__active=True,
        ):
            headquarters[availability.headquarters_id] = {
                "id": availability.headquarters_id,
                "name": availability.headquarters.name,
            }
        context["headquarters"] = list(headquarters.values())

    if hasattr(user, "patient_profile"):
        context["profile"] = "paciente"

    if user.rol == user.Role.SUPERADMIN:
        context["profile"] = "superadmin"

    return context


def build_authenticated_user_payload(user):
    clinic_context = get_user_clinic_context(user)
    return {
        "id": user.id,
        "email": user.email,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "rol": user.rol,
        "clinic_context": clinic_context,
    }


def add_user_claims(token, user):
    user_payload = build_authenticated_user_payload(user)
    token["email"] = user.email
    token["nombre"] = user.nombre
    token["apellido"] = user.apellido
    token["rol"] = user.rol
    token["clinic_context"] = user_payload["clinic_context"]
    return token


def create_auth_tokens(user):
    refresh = RefreshToken.for_user(user)
    add_user_claims(refresh, user)
    access = refresh.access_token

    expires_at = datetime.fromtimestamp(access["exp"], tz=datetime_timezone.utc)
    refresh_expires_at = datetime.fromtimestamp(refresh["exp"], tz=datetime_timezone.utc)
    return {
        "access": str(access),
        "refresh": str(refresh),
        "expires_at": expires_at,
        "refresh_expires_at": refresh_expires_at,
    }


def create_access_token(user):
    tokens = create_auth_tokens(user)
    return tokens["access"], tokens["expires_at"]


def decode_access_token(token):
    return AccessToken(token).payload


def get_access_token_lifetime_seconds():
    return int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())


def get_refresh_token_lifetime_seconds():
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
