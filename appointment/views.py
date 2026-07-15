import logging
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import F, Q

from appointment.models import Appointment
from appointment.serializers import (
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
    AppointmentListSerializer,
)
from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor
from notifications.services import send_appointment_confirmation
from patient.models import Patient
from patient.serializers import PatientListSerializer
from rules.models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction, Period
from rules.services import create_limit_alert_notifications, period_bounds as _period_bounds
from specialties.models import Specialty

logger = logging.getLogger(__name__)


def _get_patient(user):
    try:
        return user.patient_profile
    except Exception:
        raise PermissionDenied("Solo los pacientes pueden gestionar citas.")


class AppointmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):


        # --- CAMBIO PRINCIPAL PARA ADMITIR ADMINISTRATIVOS ---
        if request.user.rol == "administrativo":
            # El administrativo debe enviar el ID del paciente desde el frontend
            patient_id = request.data.get("patient_id")
            if not patient_id:
                raise ValidationError({"patient_id": "Debe proporcionar el ID del paciente para agendar la cita."})
            try:
                patient = Patient.objects.get(pk=patient_id)
            except Patient.DoesNotExist:
                raise ValidationError({"patient_id": "El paciente seleccionado no existe."})
        else:
            # Si es un paciente normal, se obtiene automáticamente de su perfil
            patient = _get_patient(request.user)
        # -----------------------------------------------------


        
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        doctor_id = data["doctor_id"]
        specialty_id = data["specialty_id"]
        scheduled_at = data["scheduled_at"]

        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at)

        with transaction.atomic():
            # Lock doctor row to serialize concurrent booking for the same doctor
            doctor = Doctor.objects.select_for_update().get(pk=doctor_id)
            specialty = Specialty.objects.get(pk=specialty_id)

            avail = self._get_availability(doctor, specialty_id, scheduled_at)
            duration_minutes = avail.appointment_duration
            slot_end = scheduled_at + timedelta(minutes=duration_minutes)

            self._check_no_schedule_exception(doctor, scheduled_at)
            self._check_slot_free(doctor, scheduled_at, slot_end)
            self._check_patient_no_overlap(patient, scheduled_at, slot_end)
            self._check_frequency_restriction(patient, specialty, scheduled_at)
            self._check_eps_limit(patient, specialty, scheduled_at)
            # Returns the locked budget row (or None) so we can discount after booking.
            budget = self._check_eps_budget(patient, specialty, scheduled_at)

            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                specialty=specialty,
                headquarters=avail.headquarters,
                scheduled_at=scheduled_at,
                duration_minutes=duration_minutes,
                status=Appointment.Status.CONFIRMED,
                created_by=request.user,
                consultation_reason=data.get("consultation_reason", ""),
            )

            if budget is not None:
                EPSBudget.objects.filter(pk=budget.pk).update(used_budget=F("used_budget") + 1)

        send_appointment_confirmation(appointment)

        try:
            # Best-effort: alerting the superadmin should never break the booking flow.
            create_limit_alert_notifications(appointment)
        except Exception:
            logger.exception("Error creando alertas de tope para la cita %s", appointment.pk)

        return Response(
            AppointmentDetailSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )

    def _get_availability(self, doctor, specialty_id, scheduled_at):
        weekday = scheduled_at.weekday()
        slot_time = scheduled_at.time()

        for avail in DoctorAvailability.objects.filter(
            doctor=doctor, specialty_id=specialty_id, active=True, weekday=weekday
        ).select_related("headquarters"):
            start_min = avail.start_time.hour * 60 + avail.start_time.minute
            slot_min = slot_time.hour * 60 + slot_time.minute
            end_min = avail.end_time.hour * 60 + avail.end_time.minute

            offset = slot_min - start_min
            # Slot must start at an aligned boundary and fit within the window
            if offset < 0:
                continue
            if offset % avail.appointment_duration != 0:
                continue
            if slot_min + avail.appointment_duration > end_min:
                continue
            return avail

        raise ValidationError(
            {"scheduled_at": "La franja horaria seleccionada no corresponde a una disponibilidad válida del médico."}
        )

    def _check_no_schedule_exception(self, doctor, scheduled_at):
        if ScheduleException.objects.filter(doctor=doctor, date=scheduled_at.date()).exists():
            raise ValidationError(
                {"scheduled_at": "El médico no tiene disponibilidad en esa fecha."}
            )

    def _check_slot_free(self, doctor, slot_start, slot_end):
        for appt in Appointment.objects.filter(
            doctor=doctor,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            scheduled_at__lt=slot_end,
        ):
            appt_end = appt.scheduled_at + timedelta(minutes=appt.duration_minutes)
            if appt_end > slot_start:
                raise ValidationError({"scheduled_at": "Esta franja ya no está disponible."})

    def _check_patient_no_overlap(self, patient, slot_start, slot_end):
        for appt in Appointment.objects.filter(
            patient=patient,
            status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
            scheduled_at__lt=slot_end,
        ):
            appt_end = appt.scheduled_at + timedelta(minutes=appt.duration_minutes)
            if appt_end > slot_start:
                raise ValidationError(
                    {"scheduled_at": "El paciente ya tiene una cita agendada en ese horario."}
                )

    def _check_frequency_restriction(self, patient, specialty, scheduled_at):
        restrictions = FrequencyRestriction.objects.filter(
            Q(specialty=specialty) | Q(specialty__isnull=True)
        )
        for restriction in restrictions:
            period_start, period_end = _period_bounds(scheduled_at, restriction.period)
            appointments = Appointment.objects.filter(
                patient=patient,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
                scheduled_at__date__gte=period_start,
                scheduled_at__date__lte=period_end,
            )
            if restriction.specialty_id is not None:
                appointments = appointments.filter(specialty=specialty)
            count = appointments.count()
            if count >= restriction.max_appointments_per_patient:
                label = "semana" if restriction.period == Period.WEEKLY else "mes"
                raise ValidationError(
                    {
                        "detail": (
                            f"Has alcanzado el límite de {restriction.max_appointments_per_patient} "
                            f"cita(s) por {label} para la especialidad {specialty.name}."
                        )
                    }
                )

    def _check_eps_limit(self, patient, specialty, scheduled_at):
        if not patient.eps:
            return
        # select_for_update locks the matching limit rows so concurrent bookings for the
        # same EPS (even across different doctors) are serialized and cannot both pass
        # the count check before either has committed its new appointment.
        # order_by() clears the model's default ordering, which otherwise pulls in an
        # implicit LEFT OUTER JOIN on the nullable "specialty" FK (via Specialty's own
        # default ordering) — Postgres refuses to lock rows on the nullable side of an
        # outer join ("FOR UPDATE cannot be applied to the nullable side of an outer join").
        limits = EPSAppointmentLimit.objects.select_for_update().filter(
            Q(specialty=specialty) | Q(specialty__isnull=True),
            eps=patient.eps,
            active=True,
        ).order_by("pk")
        for limit in limits:
            period_start, period_end = _period_bounds(scheduled_at, limit.period)
            appointments = Appointment.objects.filter(
                patient__eps=patient.eps,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
                scheduled_at__date__gte=period_start,
                scheduled_at__date__lte=period_end,
            )
            if limit.specialty_id is not None:
                appointments = appointments.filter(specialty=specialty)
            count = appointments.count()
            if count >= limit.max_appointments:
                label = "semana" if limit.period == Period.WEEKLY else "mes"
                raise ValidationError(
                    {
                        "detail": (
                            f"Tu EPS ha alcanzado el tope de {limit.max_appointments} "
                            f"cita(s) por {label} para esta especialidad."
                        )
                    }
                )

    def _check_eps_budget(self, patient, specialty, scheduled_at):
        """Returns the matching EPSBudget row (locked) so the caller can discount it, or None."""
        if not patient.eps:
            return None
        appt_date = scheduled_at.date()
        # select_for_update prevents two concurrent bookings from both passing the budget check
        budget = (
            EPSBudget.objects.select_for_update()
            .filter(
                Q(specialty=specialty) | Q(specialty__isnull=True),
                eps=patient.eps,
                period_start__lte=appt_date,
                period_end__gte=appt_date,
            )
            .first()
        )
        if budget and budget.used_budget >= budget.total_budget:
            raise ValidationError(
                {"detail": "Tu EPS no tiene disponibilidad presupuestal para agendar esta cita."}
            )
        return budget


class AppointmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient = _get_patient(request.user)
        appointments = (
            Appointment.objects.filter(patient=patient)
            .select_related("doctor__user", "specialty")
            .order_by("-scheduled_at")
        )
        serializer = AppointmentListSerializer(appointments, many=True)
        return Response(serializer.data)


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        patient = _get_patient(request.user)
        try:
            appointment = Appointment.objects.select_related(
                "doctor__user", "specialty", "headquarters", "patient__user"
            ).get(pk=pk, patient=patient)
        except Appointment.DoesNotExist:
            raise ValidationError({"detail": "Cita no encontrada."})
        return Response(AppointmentDetailSerializer(appointment).data)


# ==========================================
#          BUSQUEDA PACIENTE
# ==========================================

class PatientSearchPermission(IsAuthenticated):
    def has_permission(self, request, view):
        # 1. Validamos primero si está autenticado usando el comportamiento directo
        is_authenticated = request.user and request.user.is_authenticated
        if not is_authenticated:
            return False
            
        # 2. Comparamos directamente contra el string de tu base de datos
        return request.user.rol == "administrativo"


class PatientSearchView(ListAPIView):
    permission_classes = [PatientSearchPermission]
    serializer_class = PatientListSerializer

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        if not query:
            return Patient.objects.none()

        # Filtramos pacientes con cuentas activas
        queryset = Patient.objects.filter(user__is_active=True)
        
        # Filtros de coincidencia por texto o documento
        queryset = queryset.filter(
            Q(user__nombre__icontains=query) |
            Q(user__apellido__icontains=query) |
            Q(identity_document__icontains=query) |
            Q(user__email__icontains=query)
        )
        return queryset.select_related('user', 'eps')