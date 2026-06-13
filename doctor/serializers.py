from rest_framework import serializers

from doctor.models import Doctor


class DoctorListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    specialties = serializers.SerializerMethodField()
    next_available_date = serializers.DateField(read_only=True)

    class Meta:
        model = Doctor
        fields = ["id", "full_name", "specialties", "next_available_date"]

    def get_full_name(self, obj):
        return f"{obj.user.nombre} {obj.user.apellido}"

    def get_specialties(self, obj):
        return list(obj.specialties.values("id", "name"))
