from datetime import date, datetime, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from appointment.models import Appointment
from availability.models import DoctorAvailability, ScheduleException
from availability.serializers import SlotSerializer


class AvailableSlotsView(APIView):
    """
    GET /api/availability/slots/

    Modes:
      1. By doctor+specialty (original):
         ?doctor=<id>&specialty=<id>[&date=<YYYY-MM-DD>][&view=week|month]

      2. By specialty+headquarters (HU14):
         ?specialty=<id>&headquarters=<id>[&date_from=<YYYY-MM-DD>][&date_to=<YYYY-MM-DD>]
         Returns all free slots across all doctors in that sede+specialty,
         including the sede address and consulting room for each slot.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor_id = request.query_params.get("doctor")
        specialty_id = request.query_params.get("specialty")
        headquarters_id = request.query_params.get("headquarters")

        if not specialty_id:
            raise ValidationError({"specialty": "El parámetro 'specialty' es requerido."})

        if headquarters_id and not doctor_id:
            return self._slots_by_headquarters(request, specialty_id, headquarters_id)

        if not doctor_id:
            raise ValidationError({"detail": "Debe proporcionar 'doctor' o 'headquarters' junto con 'specialty'."})

        # Original mode: slots for a specific doctor
        date_str = request.query_params.get("date")
        view = request.query_params.get("view", "week")

        try:
            start_date = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            raise ValidationError({"date": "Formato inválido. Use YYYY-MM-DD."})

        end_date = start_date + timedelta(days=29 if view == "month" else 6)

        slots = self._generate_slots(doctor_id, specialty_id, start_date, end_date, headquarters_filter=headquarters_id)
        serializer = SlotSerializer(slots, many=True)
        return Response({"view": view, "start_date": start_date, "end_date": end_date, "slots": serializer.data})

    def _slots_by_headquarters(self, request, specialty_id, headquarters_id):
        date_from_str = request.query_params.get("date_from")
        date_to_str = request.query_params.get("date_to")

        try:
            start_date = date.fromisoformat(date_from_str) if date_from_str else date.today()
        except ValueError:
            raise ValidationError({"date_from": "Formato inválido. Use YYYY-MM-DD."})

        try:
            end_date = date.fromisoformat(date_to_str) if date_to_str else start_date + timedelta(days=29)
        except ValueError:
            raise ValidationError({"date_to": "Formato inválido. Use YYYY-MM-DD."})

        if end_date < start_date:
            raise ValidationError({"date_to": "La fecha de fin debe ser mayor o igual a la de inicio."})

        # Collect all doctors with availability in this sede+specialty
        doctor_ids = (
            DoctorAvailability.objects.filter(
                specialty_id=specialty_id,
                headquarters_id=headquarters_id,
                active=True,
            )
            .values_list("doctor_id", flat=True)
            .distinct()
        )

        all_slots = []
        for doctor_id in doctor_ids:
            all_slots.extend(
                self._generate_slots(doctor_id, specialty_id, start_date, end_date, headquarters_filter=headquarters_id)
            )

        all_slots.sort(key=lambda s: (s["date"], s["start_time"]))
        serializer = SlotSerializer(all_slots, many=True)
        return Response({
            "specialty_id": int(specialty_id),
            "headquarters_id": int(headquarters_id),
            "start_date": start_date,
            "end_date": end_date,
            "slots": serializer.data,
        })

    def _generate_slots(self, doctor_id, specialty_id, start_date, end_date, headquarters_filter=None):
        avail_qs = DoctorAvailability.objects.filter(
            doctor_id=doctor_id,
            specialty_id=specialty_id,
            active=True,
        ).select_related("headquarters", "doctor__user")

        if headquarters_filter:
            avail_qs = avail_qs.filter(headquarters_id=headquarters_filter)

        availabilities = list(avail_qs)

        if not availabilities:
            return []

        exception_dates = set(
            ScheduleException.objects.filter(
                doctor_id=doctor_id,
                date__range=(start_date, end_date),
            ).values_list("date", flat=True)
        )

        booked_appointments = list(
            Appointment.objects.filter(
                doctor_id=doctor_id,
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING],
                scheduled_at__date__range=(start_date, end_date),
            ).values("scheduled_at", "duration_minutes")
        )

        now = timezone.now()
        slots = []
        current_date = start_date

        while current_date <= end_date:
            if current_date not in exception_dates:
                weekday = current_date.weekday()
                day_availabilities = [a for a in availabilities if a.weekday == weekday]

                for avail in day_availabilities:
                    slot_start = datetime.combine(current_date, avail.start_time)
                    slot_end = datetime.combine(current_date, avail.end_time)
                    duration = timedelta(minutes=avail.appointment_duration)

                    current_slot = slot_start
                    while current_slot + duration <= slot_end:
                        slot_end_dt = current_slot + duration

                        slot_start_aware = timezone.make_aware(current_slot)
                        if slot_start_aware <= now:
                            current_slot += duration
                            continue

                        if not self._is_booked(current_slot, slot_end_dt, booked_appointments):
                            doctor_name = None
                            if avail.doctor and avail.doctor.user:
                                doctor_name = f"Dr(a). {avail.doctor.user.nombre} {avail.doctor.user.apellido}"
                            slots.append(
                                {
                                    "date": current_date,
                                    "start_time": current_slot.time(),
                                    "end_time": slot_end_dt.time(),
                                    "duration_minutes": avail.appointment_duration,
                                    "doctor_id": int(doctor_id),
                                    "doctor_name": doctor_name,
                                    "headquarters_id": avail.headquarters_id,
                                    "headquarters_name": avail.headquarters.name if avail.headquarters else None,
                                    "headquarters_address": avail.headquarters.address if avail.headquarters else None,
                                    "consulting_room": avail.consulting_room or None,
                                }
                            )
                        current_slot += duration

            current_date += timedelta(days=1)

        return slots

    def _is_booked(self, slot_start, slot_end, booked_appointments):
        for appt in booked_appointments:
            appt_start = timezone.make_naive(appt["scheduled_at"]) if timezone.is_aware(appt["scheduled_at"]) else appt["scheduled_at"]
            appt_end = appt_start + timedelta(minutes=appt["duration_minutes"])
            if appt_start < slot_end and appt_end > slot_start:
                return True
        return False
