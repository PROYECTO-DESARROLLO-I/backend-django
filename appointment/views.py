from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q

from appointment.models import Appointment
from appointment.serializers import (
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
    AppointmentListSerializer,
)
from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor
from notifications.services import send_appointment_confirmation
from rules.models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction, Period
from specialties.models import Specialty


def _get_patient(user):
    try:
        return user.patient_profile
    except Exception:
        raise PermissionDenied("Solo los pacientes pueden gestionar citas.")


class AppointmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient = _get_patient(request.user)
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
            self._check_eps_budget(patient, specialty, scheduled_at)

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

        send_appointment_confirmation(appointment)

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
                    {"scheduled_at": "Ya tienes una cita agendada en ese horario."}
                )

    def _check_frequency_restriction(self, patient, specialty, scheduled_at):
        restrictions = FrequencyRestriction.objects.filter(
            Q(specialty=specialty) | Q(specialty__isnull=True)
        )
        for restriction in restrictions:
            period_start, period_end = _period_bounds(scheduled_at, restriction.period)
            count = Appointment.objects.filter(
                patient=patient,
                specialty=specialty,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
                scheduled_at__date__gte=period_start,
                scheduled_at__date__lte=period_end,
            ).count()
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
        limits = EPSAppointmentLimit.objects.filter(
            Q(specialty=specialty) | Q(specialty__isnull=True),
            eps=patient.eps,
            active=True,
        )
        for limit in limits:
            period_start, period_end = _period_bounds(scheduled_at, limit.period)
            count = Appointment.objects.filter(
                patient=patient,
                specialty=specialty,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
                scheduled_at__date__gte=period_start,
                scheduled_at__date__lte=period_end,
            ).count()
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
        if not patient.eps:
            return
        appt_date = scheduled_at.date()
        budget = (
            EPSBudget.objects.filter(
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


def _period_bounds(scheduled_at, period):
    from datetime import timedelta as _td
    appt_date = scheduled_at.date() if hasattr(scheduled_at, "date") else scheduled_at
    if period == Period.WEEKLY:
        monday = appt_date - _td(days=appt_date.weekday())
        return monday, monday + _td(days=6)
    else:
        first = appt_date.replace(day=1)
        if first.month == 12:
            last = first.replace(day=31)
        else:
            last = first.replace(month=first.month + 1) - _td(days=1)
        return first, last
