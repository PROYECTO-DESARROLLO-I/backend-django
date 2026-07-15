from rest_framework import serializers
from appointment.models import Appointment


class AppointmentDashboardSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_document = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    specialty_name = serializers.SerializerMethodField()
    headquarters_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_name',
            'patient_document',
            'doctor_name',
            'specialty_name',
            'headquarters_name',
            'scheduled_at',
            'duration_minutes',
            'status',
            'consultation_reason',
        ]

    def get_patient_name(self, obj):
        u = obj.patient.user
        return f"{u.nombre} {u.apellido}"

    def get_patient_document(self, obj):
        return obj.patient.identity_document

    def get_doctor_name(self, obj):
        u = obj.doctor.user
        return f"{u.nombre} {u.apellido}"

    def get_specialty_name(self, obj):
        return obj.specialty.name

    def get_headquarters_name(self, obj):
        return obj.headquarters.name if obj.headquarters else None