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
    GET /api/availability/slots/?doctor=<id>&specialty=<id>&date=<YYYY-MM-DD>&view=week|month
    Returns free time slots for a doctor+specialty combination.
    Default view is weekly (7 days from the requested date).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor_id = request.query_params.get("doctor")
        specialty_id = request.query_params.get("specialty")
        date_str = request.query_params.get("date")
        view = request.query_params.get("view", "week")

        if not doctor_id or not specialty_id:
            raise ValidationError({"detail": "Los parámetros 'doctor' y 'specialty' son requeridos."})

        try:
            start_date = date.fromisoformat(date_str) if date_str else date.today()
        except ValueError:
            raise ValidationError({"date": "Formato inválido. Use YYYY-MM-DD."})

        if view == "month":
            end_date = start_date + timedelta(days=29)
        else:
            end_date = start_date + timedelta(days=6)

        slots = self._generate_slots(doctor_id, specialty_id, start_date, end_date)
        serializer = SlotSerializer(slots, many=True)
        return Response({"view": view, "start_date": start_date, "end_date": end_date, "slots": serializer.data})

    def _generate_slots(self, doctor_id, specialty_id, start_date, end_date):
        availabilities = list(
            DoctorAvailability.objects.filter(
                doctor_id=doctor_id,
                specialty_id=specialty_id,
                active=True,
            ).select_related("headquarters")
        )

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

                        # Skip past slots
                        slot_start_aware = timezone.make_aware(current_slot)
                        if slot_start_aware <= now:
                            current_slot += duration
                            continue

                        if not self._is_booked(current_slot, slot_end_dt, booked_appointments):
                            slots.append(
                                {
                                    "date": current_date,
                                    "start_time": current_slot.time(),
                                    "end_time": slot_end_dt.time(),
                                    "duration_minutes": avail.appointment_duration,
                                    "headquarters_id": avail.headquarters_id,
                                    "headquarters_name": avail.headquarters.name if avail.headquarters else None,
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
