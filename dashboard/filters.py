from django.db.models import Q


def apply_appointment_filters(queryset, params):
    """
    Aplica filtros combinables al queryset de Appointment.
    Recibe request.query_params y devuelve el queryset filtrado.
    """
    date_from   = params.get('date_from')
    date_to     = params.get('date_to')
    doctor_id   = params.get('doctor_id')
    doctor_name = params.get('doctor_name')
    specialty   = params.get('specialty')
    status      = params.get('status')
    patient_doc = params.get('patient_document')
    patient_name= params.get('patient_name')

    if date_from:
        queryset = queryset.filter(scheduled_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(scheduled_at__date__lte=date_to)
    if doctor_id:
        queryset = queryset.filter(doctor__id=doctor_id)
    if doctor_name:
        queryset = queryset.filter(
            Q(doctor__user__nombre__icontains=doctor_name) |
            Q(doctor__user__apellido__icontains=doctor_name)
        )
    if specialty:
        queryset = queryset.filter(specialty__id=specialty)
    if status:
        queryset = queryset.filter(status=status)
    if patient_doc:
        queryset = queryset.filter(
            patient__identity_document__icontains=patient_doc
        )
    if patient_name:
        queryset = queryset.filter(
            Q(patient__user__nombre__icontains=patient_name) |
            Q(patient__user__apellido__icontains=patient_name)
        )

    return queryset