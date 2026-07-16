from rest_framework import serializers

from specialties.models import Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    available_doctors_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Specialty
        fields = ["id", "name", "description", "available_doctors_count"]

class SpecialtyAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ['id', 'name', 'description', 'active']

    def validate_name(self, value):
        qs = Specialty.objects.filter(name__iexact=value)
        # En update, excluir la instancia actual
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ya existe una especialidad con este nombre."
            )
        return value