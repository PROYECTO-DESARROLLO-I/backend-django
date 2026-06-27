from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from eps.models import EPS
from user.serializers import UserResponseSerializer, UserSignupSerializer

from .models import Patient
from headquarters.models import Headquarters
from django.db.models import Count
User = get_user_model()


class PatientRegistrationSerializer(serializers.ModelSerializer):
    user = UserSignupSerializer()
    eps = serializers.PrimaryKeyRelatedField(
        queryset=EPS.objects.filter(active=True),
        required=True,
        allow_null=False,
    )
    
    class Meta:
        model = Patient
        fields = [
            "user",
            "document_type",
            "identity_document",
            "date_birth",
            "phone_number",
            "address",
            "eps",
        ]

    
    def validate_date_birth(self, value: date | None) -> date | None:
        if value is None:
            return value
        if value > date.today():
            raise serializers.ValidationError("La fecha de nacimiento no puede ser futura.")
        return value

    @transaction.atomic
    def create(self, validated_data: dict) -> Patient:
        user_data = validated_data.pop("user")

        user = User.objects.create_user(
            email=user_data["email"],
            password=user_data["password"],
            nombre=user_data["nombre"],
            apellido=user_data["apellido"],
            rol=User.Role.PATIENT,
        )

        # 2. ALGORITMO: Buscar la sede con menos pacientes asignados (sólo sedes activas)
        # .annotate crea un campo temporal 'num_pacientes' contando las relaciones de la tabla pacientes.
        # .order_by lo organiza de menor a mayor.
        # .first() toma la sede con el número más bajo. Si no hay sedes en la BD, devuelve None.
        sede_automatica = Headquarters.objects.filter(active=True).annotate(
            num_pacientes=Count("pacientes")
        ).order_by("num_pacientes").first()

        patient = Patient.objects.create(user=user, 
                                        sede=sede_automatica,
                                         **validated_data 
                                         )
        return patient

    def to_representation(self, instance: Patient) -> dict:
        return {
            "id": instance.id,
            "user": UserResponseSerializer(instance.user).data,
            "identity_document": instance.identity_document,
            "document_type": instance.document_type,
            "date_birth": instance.date_birth,
            "phone_number": instance.phone_number,
            "address": instance.address,
            "sede": {
                "id": instance.sede_id,
                "name": instance.sede.name if instance.sede else None,
            },
            "eps": {
                "id": instance.eps_id,
                "name": instance.eps.get_name_display() if instance.eps else None,
            },
        }



class PatientListSerializer(serializers.ModelSerializer):
    user = UserResponseSerializer(read_only=True) 

    class Meta:
        model = Patient
        fields = [
            "id", 
            "identity_document", 
            "document_type", 
            "user"
        ]