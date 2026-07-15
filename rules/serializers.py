from rest_framework import serializers

from rules.models import EPSAppointmentLimit, EPSBudget, FrequencyRestriction


class EPSAppointmentLimitSerializer(serializers.ModelSerializer):
    eps_name = serializers.SerializerMethodField()
    specialty_name = serializers.SerializerMethodField()

    class Meta:
        model = EPSAppointmentLimit
        fields = [
            "id",
            "eps",
            "eps_name",
            "specialty",
            "specialty_name",
            "period",
            "max_appointments",
            "active",
        ]
        # Disable DRF's auto-generated validator for the model's UniqueConstraint so we
        # can raise our own friendly Spanish message from validate() instead of the
        # generic "deben formar un conjunto único" one.
        validators = []

    def get_eps_name(self, obj):
        return str(obj.eps)

    def get_specialty_name(self, obj):
        return obj.specialty.name if obj.specialty else None

    def validate_max_appointments(self, value):
        if value <= 0:
            raise serializers.ValidationError("El número máximo de citas debe ser mayor a cero.")
        return value

    def validate(self, attrs):
        eps = attrs.get("eps", getattr(self.instance, "eps", None))
        specialty = attrs.get("specialty", getattr(self.instance, "specialty", None))
        period = attrs.get("period", getattr(self.instance, "period", None))
        active = attrs.get("active", getattr(self.instance, "active", True))

        if active:
            duplicates = EPSAppointmentLimit.objects.filter(
                eps=eps, specialty=specialty, period=period, active=True
            )
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    "Ya existe un tope activo para esta EPS, especialidad y periodo."
                )
        return attrs


class EPSBudgetSerializer(serializers.ModelSerializer):
    eps_name = serializers.SerializerMethodField()
    specialty_name = serializers.SerializerMethodField()

    class Meta:
        model = EPSBudget
        fields = [
            "id",
            "eps",
            "eps_name",
            "specialty",
            "specialty_name",
            "period_start",
            "period_end",
            "total_budget",
            "used_budget",
        ]
        read_only_fields = ["used_budget"]

    def get_eps_name(self, obj):
        return str(obj.eps)

    def get_specialty_name(self, obj):
        return obj.specialty.name if obj.specialty else None

    def validate_total_budget(self, value):
        if value < 0:
            raise serializers.ValidationError("El presupuesto total no puede ser negativo.")
        return value

    def validate(self, attrs):
        period_start = attrs.get("period_start", getattr(self.instance, "period_start", None))
        period_end = attrs.get("period_end", getattr(self.instance, "period_end", None))
        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError(
                {"period_end": "La fecha de fin del periodo debe ser posterior o igual a la fecha de inicio."}
            )
        return attrs


class FrequencyRestrictionSerializer(serializers.ModelSerializer):
    specialty_name = serializers.SerializerMethodField()

    class Meta:
        model = FrequencyRestriction
        fields = [
            "id",
            "specialty",
            "specialty_name",
            "period",
            "max_appointments_per_patient",
        ]

    def get_specialty_name(self, obj):
        return obj.specialty.name if obj.specialty else None

    def validate_max_appointments_per_patient(self, value):
        if value <= 0:
            raise serializers.ValidationError("El número máximo de citas por paciente debe ser mayor a cero.")
        return value
