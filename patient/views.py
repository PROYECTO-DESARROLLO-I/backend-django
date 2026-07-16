from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
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
