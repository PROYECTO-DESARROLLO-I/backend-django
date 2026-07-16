from itertools import count

from rest_framework import serializers
from .models import Headquarters

class HeadquartersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Headquarters
        fields = ["id", "name", "address", "phone", "active"]


class HeadquartersCreateSerializer(serializers.ModelSerializer):
    """Serializer used to create a new sede (headquarters)."""

    class Meta:
        model = Headquarters
        fields = ["id", "name", "address", "phone", "active"]

    def validate_name(self, value):
        if Headquarters.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una sede con este nombre.")
        return value

#se puede añadir a futuro un metodo para obtener la sede con menos carga de pacientes
"""
def obtener_sede_con_menos_carga():
    # Cuenta cuántos usuarios tiene cada sede y trae la que tenga menos
    # Al usar null=True, las sedes vacías devolverán 0 y serán elegidas primero
    sede = Headquarters.objects.annotate(
        total_usuarios=count('usuarios')
    ).order_by('total_usuarios').first()
    
    return sede
"""
