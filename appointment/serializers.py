from rest_framework import serializers

from appointment.models import Appointment
from doctor.models import Doctor
from specialties.models import Specialty


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    specialty_id = serializers.IntegerField()
    headquarters_id = serializers.IntegerField()
    scheduled_at = serializers.DateTimeField()
    consultation_reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_doctor_id(self, value):
        if not Doctor.objects.filter(pk=value, active=True).exists():
            raise serializers.ValidationError("El médico no existe o no está activo.")
        return value

    def validate_specialty_id(self, value):
        if not Specialty.objects.filter(pk=value, active=True).exists():
            raise serializers.ValidationError("La especialidad no existe o no está activa.")
        return value

    def validate_headquarters_id(self, value):
        from headquarters.models import Headquarters
        if not Headquarters.objects.filter(pk=value, active=True).exists():
            raise serializers.ValidationError("La sede no existe o no está activa.")
        return value


class AppointmentDetailSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    specialty_name = serializers.SerializerMethodField()
    headquarters_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient_name",
            "doctor_name",
            "specialty_name",
            "headquarters_name",
            "scheduled_at",
            "duration_minutes",
            "status",
            "consultation_reason",
            "notes",
            "created_at",
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.user.nombre} {obj.patient.user.apellido}"

    def get_doctor_name(self, obj):
        return f"Dr(a). {obj.doctor.user.nombre} {obj.doctor.user.apellido}"

    def get_specialty_name(self, obj):
        return obj.specialty.name

    def get_headquarters_name(self, obj):
        return obj.headquarters.name if obj.headquarters else None


class AppointmentListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    specialty_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = ["id", "doctor_name", "specialty_name", "scheduled_at", "duration_minutes", "status"]

    def get_doctor_name(self, obj):
        return f"Dr(a). {obj.doctor.user.nombre} {obj.doctor.user.apellido}"

    def get_specialty_name(self, obj):
        return obj.specialty.name


class DoctorAppointmentListSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    specialty_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = ["id", "patient_name", "specialty_name", "scheduled_at", "duration_minutes", "status"]

    def get_patient_name(self, obj):
        return f"{obj.patient.user.nombre} {obj.patient.user.apellido}"

    def get_specialty_name(self, obj):
        return obj.specialty.name


class AppointmentRescheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
