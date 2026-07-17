from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from appointment.models import Appointment, AppointmentHistory
from appointment.services import _refund_eps_budget
from notifications.services import send_appointment_cancelled
from user.permissions import IsAdministrativeUser

from .models import Patient
from .serializers import (
    PatientListSerializer,
    PatientProfileSerializer,
    PatientProfileUpdateSerializer,
    PatientRegistrationSerializer,
)

_ACTIVE_APPOINTMENT_STATUSES = [
    Appointment.Status.PENDING,
    Appointment.Status.CONFIRMED,
    Appointment.Status.RESCHEDULED,
]


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


def _cancel_future_appointments(patient, changed_by):
    """Cancela, dentro de la transacción actual, las citas futuras activas del
    paciente. Devuelve la lista de citas canceladas para notificar luego."""
    appointments = list(
        Appointment.objects.select_for_update(of=("self",))
        .select_related("patient__user", "doctor__user", "specialty", "headquarters")
        .filter(
            patient=patient,
            scheduled_at__gt=timezone.now(),
            status__in=_ACTIVE_APPOINTMENT_STATUSES,
        )
    )

    reason = "Cancelación automática por desactivación de la cuenta del paciente"
    for appointment in appointments:
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])

        AppointmentHistory.objects.create(
            appointment=appointment,
            previous_scheduled_at=appointment.scheduled_at,
            new_scheduled_at=appointment.scheduled_at,
            changed_by=changed_by,
            reason=reason,
        )

        _refund_eps_budget(appointment.patient, appointment.specialty, appointment.scheduled_at)

    return appointments


def _set_patient_status(pk, is_active, already_message, request_user=None):
    with transaction.atomic():
        patient = get_object_or_404(
            Patient.objects.select_for_update(of=("self", "user")).select_related("user"),
            pk=pk,
        )
        user = patient.user

        if user.is_active == is_active:
            return Response(
                {"detail": already_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = is_active
        user.save(update_fields=["is_active", "updated_at"])

        cancelled_appointments = []
        if not is_active:
            cancelled_appointments = _cancel_future_appointments(patient, request_user)

    # Notificaciones fuera de la transacción, igual que AppointmentCancelView.
    for appointment in cancelled_appointments:
        send_appointment_cancelled(appointment, cancelled_by=request_user)

    data = PatientListSerializer(patient).data
    data["is_active"] = user.is_active
    data["cancelled_appointments"] = {
        "count": len(cancelled_appointments),
        "ids": [appointment.pk for appointment in cancelled_appointments],
    }

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
    POST /api/patients/<id>/deactivate/ - Desactiva la cuenta del paciente y
    cancela sus citas futuras pendientes/confirmadas/reprogramadas.
    """

    permission_classes = [IsAdministrativeUser]

    def post(self, request, pk):
        return _set_patient_status(
            pk,
            is_active=False,
            already_message="El paciente ya está desactivado.",
            request_user=request.user,
        )


class PatientActivateView(APIView):
    """
    POST /api/patients/<id>/activate/ - Reactiva la cuenta del paciente.
    """

    permission_classes = [IsAdministrativeUser]

    def post(self, request, pk):
        return _set_patient_status(
            pk,
            is_active=True,
            already_message="El paciente ya está activo.",
            request_user=request.user,
        )
