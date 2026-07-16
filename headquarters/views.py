from datetime import date, timedelta

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointment.models import Appointment
from availability.models import DoctorAvailability, ScheduleException
from headquarters.models import Headquarters
from headquarters.serializers import HeadquartersCreateSerializer, HeadquartersSerializer
from patient.models import Patient
from user.models import User
from user.permissions import IsAdministrative

_ADMIN_ROLES = {User.Role.ADMINISTRATIVE, User.Role.SUPERADMIN}


class CanListHeadquarters(BasePermission):
    """
    Administrative/superadmin users can always list headquarters.
    Patients can access the search flow only if they have a Patient profile.
    """

    message = "No tiene permisos para acceder a este recurso."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.rol in _ADMIN_ROLES:
            return True
        if user.rol == User.Role.PATIENT:
            return Patient.objects.filter(user=user).exists()
        return False


class HeadquartersListView(APIView):
    """
    GET /api/headquarters/?specialty=<id>
    - Administrative/superadmin users: returns all active sedes when no
      specialty filter is provided.
    - Patients: returns sedes that have at least one doctor with the given
      specialty and free slots in the next 30 days (specialty is required).

    POST /api/headquarters/
    Allows administrative/superadmin users to create a new sede.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdministrative()]
        return [CanListHeadquarters()]

    def post(self, request):
        serializer = HeadquartersCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        headquarters = serializer.save()
        return Response(
            HeadquartersSerializer(headquarters).data, status=status.HTTP_201_CREATED
        )

    def get(self, request):
        user = request.user
        is_admin = user.is_superuser or user.rol in _ADMIN_ROLES
        specialty_id = request.query_params.get("specialty")

        if is_admin and not specialty_id:
            headquarters = Headquarters.objects.filter(active=True).order_by("name")
            return Response(HeadquartersSerializer(headquarters, many=True).data)

        if not specialty_id:
            raise ValidationError({"specialty": "Este parámetro es requerido."})

        today = date.today()
        horizon = today + timedelta(days=30)
        active_weekdays = {(today + timedelta(days=i)).weekday() for i in range(31)}

        # Sedes con disponibilidad activa para esa especialidad en los próximos 30 días
        candidate_hq_ids = (
            DoctorAvailability.objects.filter(
                specialty_id=specialty_id,
                active=True,
                weekday__in=active_weekdays,
                headquarters__isnull=False,
                headquarters__active=True,
            )
            .values_list("headquarters_id", "doctor_id")
            .distinct()
        )

        # Filtramos las que realmente tienen al menos un slot libre
        valid_hq_ids = set()
        for hq_id, doctor_id in candidate_hq_ids:
            if hq_id in valid_hq_ids:
                continue
            if self._has_free_slot(doctor_id, specialty_id, hq_id, today, horizon):
                valid_hq_ids.add(hq_id)

        headquarters = Headquarters.objects.filter(pk__in=valid_hq_ids, active=True).order_by("name")
        return Response(HeadquartersSerializer(headquarters, many=True).data)

    def _has_free_slot(self, doctor_id, specialty_id, hq_id, start_date, end_date):
        from datetime import datetime
        from django.utils import timezone

        availabilities = list(
            DoctorAvailability.objects.filter(
                doctor_id=doctor_id,
                specialty_id=specialty_id,
                headquarters_id=hq_id,
                active=True,
            )
        )
        if not availabilities:
            return False

        exception_dates = set(
            ScheduleException.objects.filter(
                doctor_id=doctor_id,
                date__range=(start_date, end_date),
            ).values_list("date", flat=True)
        )

        booked = list(
            Appointment.objects.filter(
                doctor_id=doctor_id,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
                scheduled_at__date__range=(start_date, end_date),
            ).values("scheduled_at", "duration_minutes")
        )

        now = timezone.now()
        current_date = start_date + timedelta(days=1)
        while current_date <= end_date:
            if current_date not in exception_dates:
                weekday = current_date.weekday()
                for avail in availabilities:
                    if avail.weekday != weekday:
                        continue
                    from datetime import timedelta as _td
                    slot_start = datetime.combine(current_date, avail.start_time)
                    slot_end = datetime.combine(current_date, avail.end_time)
                    duration = _td(minutes=avail.appointment_duration)
                    current_slot = slot_start
                    while current_slot + duration <= slot_end:
                        if timezone.make_aware(current_slot) > now:
                            slot_end_dt = current_slot + duration
                            if not any(
                                (timezone.make_naive(a["scheduled_at"]) if timezone.is_aware(a["scheduled_at"]) else a["scheduled_at"]) < slot_end_dt
                                and (timezone.make_naive(a["scheduled_at"]) if timezone.is_aware(a["scheduled_at"]) else a["scheduled_at"]) + _td(minutes=a["duration_minutes"]) > current_slot
                                for a in booked
                            ):
                                return True
                        current_slot += duration
            current_date += timedelta(days=1)
        return False
