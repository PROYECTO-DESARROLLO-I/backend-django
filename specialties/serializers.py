from rest_framework import serializers

from specialties.models import Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    available_doctors_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Specialty
        fields = ["id", "name", "description", "available_doctors_count"]
