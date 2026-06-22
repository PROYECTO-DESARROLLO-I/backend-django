from datetime import date, timedelta

from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from availability.models import DoctorAvailability
from specialties.models import Specialty
from specialties.serializers import SpecialtySerializer


class SpecialtyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        active_weekdays = {(today + timedelta(days=i)).weekday() for i in range(31)}

        available_doctor_ids = (
            DoctorAvailability.objects.filter(
                active=True,
                weekday__in=active_weekdays,
            )
            .values_list("doctor_id", flat=True)
            .distinct()
        )

        specialties = (
            Specialty.objects.filter(active=True)
            .annotate(
                available_doctors_count=Count(
                    "doctor_specialties__doctor",
                    filter=Q(doctor_specialties__doctor_id__in=available_doctor_ids),
                    distinct=True,
                )
            )
            .filter(available_doctors_count__gt=0)
            .order_by("name")
        )

        serializer = SpecialtySerializer(specialties, many=True)
        return Response(serializer.data)
