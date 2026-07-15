from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse

from appointment.models import Appointment
from specialties.models import Specialty
from doctor.models import Doctor

from .filters import apply_appointment_filters
from .serializers import AppointmentDashboardSerializer
from .utils.pdf_generator import generate_appointments_pdf


class DashboardKPIView(APIView):
    """
    GET /api/dashboard/kpis/
    KPIs del día: totales por estado, % cancelaciones, ocupación por médico.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()

        # Citas del día agrupadas por estado
        today_qs = Appointment.objects.filter(scheduled_at__date=today)
        by_status = today_qs.values('status').annotate(total=Count('id'))

        status_map = {row['status']: row['total'] for row in by_status}
        total_today = today_qs.count()

        confirmed  = status_map.get('confirmada', 0)
        cancelled  = status_map.get('cancelada', 0)
        attended   = status_map.get('atendida', 0)
        pending    = status_map.get('pendiente', 0)
        rescheduled= status_map.get('reprogramada', 0)

        # % cancelaciones vs realizadas
        base_pct = confirmed + cancelled + attended
        cancellation_rate = round((cancelled / base_pct) * 100, 1) if base_pct else 0

        # Ocupación por médico (citas activas hoy / total médicos activos)
        doctors_with_today = (
            today_qs
            .exclude(status='cancelada')
            .values('doctor__id', 'doctor__user__nombre', 'doctor__user__apellido')
            .annotate(appointments_today=Count('id'))
            .order_by('-appointments_today')
        )

        occupation_by_doctor = [
            {
                'doctor_id': row['doctor__id'],
                'doctor_name': f"{row['doctor__user__nombre']} {row['doctor__user__apellido']}",
                'appointments_today': row['appointments_today'],
            }
            for row in doctors_with_today
        ]

        return Response({
            'date': today,
            'total_today': total_today,
            'by_status': {
                'pending':     pending,
                'confirmed':   confirmed,
                'attended':    attended,
                'cancelled':   cancelled,
                'rescheduled': rescheduled,
            },
            'cancellation_rate_percent': cancellation_rate,
            'occupation_by_doctor': occupation_by_doctor,
        })


class AppointmentSearchView(APIView):
    """
    GET /api/dashboard/appointments/
    Búsqueda filtrada de citas con paginación simple.

    Query params: date_from, date_to, doctor_id, doctor_name,
                  specialty, status, patient_document, patient_name,
                  page, page_size
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Appointment.objects.select_related(
            'patient__user', 'doctor__user', 'specialty', 'headquarters'
        ).order_by('-scheduled_at')

        qs = apply_appointment_filters(qs, request.query_params)

        # Paginación simple
        page      = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total     = qs.count()
        start     = (page - 1) * page_size
        end       = start + page_size

        serializer = AppointmentDashboardSerializer(qs[start:end], many=True)

        return Response({
            'total':     total,
            'page':      page,
            'page_size': page_size,
            'results':   serializer.data,
        })


class SpecialtyStatsView(APIView):
    """
    GET /api/dashboard/specialties/stats/
    Demanda por especialidad en un rango de fechas.

    Query params: date_from, date_to
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Appointment.objects.all()

        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')

        if date_from:
            qs = qs.filter(scheduled_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(scheduled_at__date__lte=date_to)

        stats = (
            qs.values('specialty__id', 'specialty__name')
            .annotate(
                total=Count('id'),
                attended=Count('id', filter=Q(status='atendida')),
                cancelled=Count('id', filter=Q(status='cancelada')),
                pending=Count('id', filter=Q(status='pendiente')),
                confirmed=Count('id', filter=Q(status='confirmada')),
            )
            .order_by('-total')
        )

        data = [
            {
                'specialty_id':   row['specialty__id'],
                'specialty_name': row['specialty__name'],
                'total':          row['total'],
                'attended':       row['attended'],
                'cancelled':      row['cancelled'],
                'pending':        row['pending'],
                'confirmed':      row['confirmed'],
                'utilization_rate': round(
                    (row['attended'] / row['total']) * 100, 1
                ) if row['total'] else 0,
            }
            for row in stats
        ]

        return Response({'results': data, 'date_from': date_from, 'date_to': date_to})


class ReportExportView(APIView):
    """
    GET /api/dashboard/reports/export/
    Exporta PDF con los resultados filtrados.
    Acepta los mismos query params que AppointmentSearchView.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Appointment.objects.select_related(
            'patient__user', 'doctor__user', 'specialty', 'headquarters'
        ).order_by('-scheduled_at')

        qs = apply_appointment_filters(qs, request.query_params)

        serializer = AppointmentDashboardSerializer(qs, many=True)

        filters_applied = {
            'Desde':        request.query_params.get('date_from'),
            'Hasta':        request.query_params.get('date_to'),
            'Médico':       request.query_params.get('doctor_name'),
            'Especialidad': request.query_params.get('specialty'),
            'Estado':       request.query_params.get('status'),
            'Paciente':     request.query_params.get('patient_name'),
        }

        pdf_buffer = generate_appointments_pdf(serializer.data, filters_applied)

        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"reporte_citas_{timezone.localdate()}.pdf",
            content_type='application/pdf',
        )