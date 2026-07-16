from datetime import date, timedelta

from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.exceptions import PermissionDenied


from availability.models import DoctorAvailability
from specialties.models import Specialty
from specialties.serializers import SpecialtySerializer, SpecialtyAdminSerializer
from user.permissions import IsAdministrativeUser, IsSuperAdmin

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

class SpecialtyAdminListCreateView(APIView):
    """
    GET  /api/dashboard/specialties/        → lista todas (incluyendo inactivas)
    POST /api/dashboard/specialties/        → crear nueva especialidad
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        #self._check_superadmin(request.user)
        specialties = Specialty.objects.all().order_by('name')
        serializer = SpecialtyAdminSerializer(specialties, many=True)
        return Response(serializer.data)

    def post(self, request):
        #self._check_superadmin(request.user)
        serializer = SpecialtyAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        specialty = serializer.save()
        return Response(
            SpecialtyAdminSerializer(specialty).data,
            status=status.HTTP_201_CREATED
        )


class SpecialtyAdminDetailView(APIView):
    """
    GET    /api/dashboard/specialties/<id>/  → detalle
    PUT    /api/dashboard/specialties/<id>/  → edición completa
    PATCH  /api/dashboard/specialties/<id>/  → edición parcial (ej: solo active)
    DELETE /api/dashboard/specialties/<id>/  → desactivar (soft delete)
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def _get_specialty(self, pk):
        try:
            return Specialty.objects.get(pk=pk)
        except Specialty.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Especialidad no encontrada.")

    def get(self, request, pk):
        #self._check_superadmin(request.user)
        specialty = self._get_specialty(pk)
        return Response(SpecialtyAdminSerializer(specialty).data)

    def put(self, request, pk):
        #self._check_superadmin(request.user)
        specialty = self._get_specialty(pk)
        serializer = SpecialtyAdminSerializer(specialty, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SpecialtyAdminSerializer(specialty).data)

    def patch(self, request, pk):
        #self._check_superadmin(request.user)
        specialty = self._get_specialty(pk)
        serializer = SpecialtyAdminSerializer(
            specialty, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SpecialtyAdminSerializer(specialty).data)

    def delete(self, request, pk):
        #self._check_superadmin(request.user)
        specialty = self._get_specialty(pk)
        specialty.active = False
        specialty.save(update_fields=['active'])
        return Response(
            {"detail": f"Especialidad '{specialty.name}' desactivada correctamente."},
            status=status.HTTP_200_OK
        )