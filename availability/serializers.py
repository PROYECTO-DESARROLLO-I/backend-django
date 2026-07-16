from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from availability.models import DoctorAvailability, ScheduleException
from doctor.models import Doctor
from headquarters.models import Headquarters
from specialties.models import Specialty


class SlotSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    duration_minutes = serializers.IntegerField()
    doctor_id = serializers.IntegerField(allow_null=True)
    doctor_name = serializers.CharField(allow_null=True)
    headquarters_id = serializers.IntegerField(allow_null=True)
    headquarters_name = serializers.CharField(allow_null=True)
    headquarters_address = serializers.CharField(allow_null=True)
    consulting_room = serializers.CharField(allow_null=True)


class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)
    headquarters_name = serializers.CharField(source="headquarters.name", read_only=True)
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = DoctorAvailability
        fields = [
            "id",
            "specialty",
            "specialty_name",
            "headquarters",
            "headquarters_name",
            "weekday",
            "weekday_display",
            "start_time",
            "end_time",
            "appointment_duration",
            "consulting_room",
            "active",
        ]
        read_only_fields = ["id"]


class DoctorAvailabilityCreateSerializer(serializers.Serializer):
    specialty = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.filter(active=True))
    headquarters = serializers.PrimaryKeyRelatedField(
        queryset=Headquarters.objects.filter(active=True),
        required=False,
        allow_null=True,
    )
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    appointment_duration = serializers.IntegerField(min_value=1)
    consulting_room = serializers.CharField(max_length=50, required=False, allow_blank=True)
    active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        doctor = self.context["doctor"]

        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError({
                "end_time": "La hora de fin debe ser posterior a la hora de inicio."
            })

        if not doctor.specialties.filter(pk=attrs["specialty"].pk, active=True).exists():
            raise serializers.ValidationError({
                "specialty": "Solo puedes asignarte disponibilidad en tus especialidades."
            })

        return attrs

    def create(self, validated_data):
        doctor = self.context["doctor"]
        availability = DoctorAvailability(doctor=doctor, **validated_data)
        try:
            availability.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        availability.save()
        return availability


class AdminDoctorAvailabilityCreateSerializer(serializers.Serializer):
    """Used by administrative/superadmin users to create a jornada for any doctor."""

    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(active=True))
    specialty = serializers.PrimaryKeyRelatedField(queryset=Specialty.objects.filter(active=True))
    headquarters = serializers.PrimaryKeyRelatedField(
        queryset=Headquarters.objects.filter(active=True),
        required=False,
        allow_null=True,
    )
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    appointment_duration = serializers.IntegerField(min_value=1)
    consulting_room = serializers.CharField(max_length=50, required=False, allow_blank=True)
    active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError({
                "end_time": "La hora de fin debe ser posterior a la hora de inicio."
            })

        doctor = attrs["doctor"]
        if not doctor.specialties.filter(pk=attrs["specialty"].pk, active=True).exists():
            raise serializers.ValidationError({
                "specialty": "El médico no tiene asignada esta especialidad."
            })

        return attrs

    def create(self, validated_data):
        availability = DoctorAvailability(**validated_data)
        try:
            availability.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        availability.save()
        return availability


class ScheduleExceptionSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleException
        fields = ["id", "doctor", "doctor_name", "date", "reason", "type"]
        read_only_fields = ["id"]

    def get_doctor_name(self, instance):
        if instance.doctor and instance.doctor.user:
            return f"{instance.doctor.user.nombre} {instance.doctor.user.apellido}"
        return None
