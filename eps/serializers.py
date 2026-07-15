from rest_framework import serializers

from eps.models import EPS


class EPSSerializer(serializers.ModelSerializer):
    class Meta:
        model = EPS
        fields = ["id", "name", "code", "active"]
        # Disable DRF's auto-generated UniqueValidator for "code" (generic English-ish
        # message) so our validate_code() below can raise a friendly Spanish message.
        extra_kwargs = {"code": {"validators": []}}

    def validate_code(self, value):
        queryset = EPS.objects.filter(code__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ya existe una EPS registrada con este código.")
        return value
