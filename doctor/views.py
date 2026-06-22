from datetime import date, timedelta

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor
from doctor.serializers import DoctorCreateSerializer, DoctorDetailSerializer, DoctorListSerializer
from notifications.services import send_doctor_welcome
from user.permissions import IsAdministrative


class DoctorView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdministrative()]
        return [IsAuthenticated()]

    def get(self, request):
        specialty_id = request.query_params.get("specialty")
        if not specialty_id:
            raise ValidationError({"specialty": "Este parámetro es requerido."})

        today = date.today()
        horizon = today + timedelta(days=30)

        doctors = (
            Doctor.objects.filter(
                active=True,
                specialties__id=specialty_id,
                specialties__active=True,
            )
            .select_related("user")
            .prefetch_related("specialties")
            .distinct()
        )

        result = []
        for doctor in doctors:
            next_date = self._next_available_date(doctor, specialty_id, today, horizon)
            if next_date is not None:
                doctor.next_available_date = next_date
                result.append(doctor)

        return Response(DoctorListSerializer(result, many=True).data)

    def post(self, request):
        serializer = DoctorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doctor = serializer.save()

        send_doctor_welcome(doctor)

        return Response(DoctorDetailSerializer(doctor).data, status=status.HTTP_201_CREATED)

    def _next_available_date(self, doctor, specialty_id, today, horizon):
        availabilities = DoctorAvailability.objects.filter(
            doctor=doctor,
            specialty_id=specialty_id,
            active=True,
        ).values_list("weekday", flat=True)

        if not availabilities:
            return None

        available_weekdays = set(availabilities)

        exception_dates = set(
            ScheduleException.objects.filter(
                doctor=doctor,
                date__range=(today, horizon),
            ).values_list("date", flat=True)
        )

        current = today + timedelta(days=1)
        while current <= horizon:
            if current.weekday() in available_weekdays and current not in exception_dates:
                return current
            current += timedelta(days=1)

        return None
