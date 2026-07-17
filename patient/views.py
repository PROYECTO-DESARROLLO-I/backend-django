from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from user.permissions import IsAdministrativeUser

from .models import Patient
from .serializers import (
    PatientListSerializer,
    PatientProfileSerializer,
    PatientProfileUpdateSerializer,
    PatientRegistrationSerializer,
)


def _get_patient(user):
    try:
        return user.patient_profile
    except Exception:
        raise PermissionDenied("Solo los pacientes pueden acceder a este recurso.")


class RegisterPatientView(generics.CreateAPIView):
    serializer_class = PatientRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class PatientMeView(APIView):
    """
    GET /api/patients/me/ - Devuelve el perfil del paciente autenticado.
    PATCH /api/patients/me/ - Permite editar solo email y teléfono.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient = _get_patient(request.user)
        return Response(PatientProfileSerializer(patient).data)

    def patch(self, request):
        patient = _get_patient(request.user)
        serializer = PatientProfileUpdateSerializer(
            data=request.data,
            context={"patient": patient, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "email" in data:
            patient.user.email = data["email"]
            patient.user.save(update_fields=["email"])
        if "phone_number" in data:
            patient.phone_number = data["phone_number"]
            patient.save(update_fields=["phone_number"])

        return Response(
            {
                "message": "Perfil actualizado correctamente",
                "data": PatientProfileSerializer(patient).data,
            }
        )


def _set_patient_status(pk, is_active, already_message):
    patient = get_object_or_404(Patient.objects.select_related("user"), pk=pk)
    user = patient.user

    if user.is_active == is_active:
        return Response(
            {"detail": already_message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.is_active = is_active
    user.save(update_fields=["is_active", "updated_at"])

    data = PatientListSerializer(patient).data
    data["is_active"] = user.is_active

    return Response(
        {
            "message": "Paciente activado correctamente"
            if is_active
            else "Paciente desactivado correctamente",
            "data": data,
        }
    )


class PatientDeactivateView(APIView):
    """
    POST /api/patients/<id>/deactivate/ - Desactiva la cuenta del paciente.
    """

    permission_classes = [IsAdministrativeUser]

    def post(self, request, pk):
        return _set_patient_status(
            pk, is_active=False, already_message="El paciente ya está desactivado."
        )


class PatientActivateView(APIView):
    """
    POST /api/patients/<id>/activate/ - Reactiva la cuenta del paciente.
    """

    permission_classes = [IsAdministrativeUser]

    def post(self, request, pk):
        return _set_patient_status(
            pk, is_active=True, already_message="El paciente ya está activo."
        )
