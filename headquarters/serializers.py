<<<<<<< HEAD
from rest_framework import serializers

from headquarters.models import Headquarters

=======
from itertools import count

from rest_framework import serializers
from .models import Headquarters
>>>>>>> origin/main

class HeadquartersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Headquarters
<<<<<<< HEAD
        fields = ["id", "name", "address", "phone"]
=======
        fields = ["id", "name", "address", "phone", "active"]

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
>>>>>>> origin/main
