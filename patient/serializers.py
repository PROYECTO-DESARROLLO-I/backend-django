from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from eps.models import EPS
from user.serializers import UserResponseSerializer, UserSignupSerializer

from .models import Patient

User = get_user_model()


class PatientRegistrationSerializer(serializers.ModelSerializer):
    user = UserSignupSerializer()
    eps = serializers.PrimaryKeyRelatedField(
        queryset=EPS.objects.filter(active=True),
        required=False,
        allow_null=True,
    )
    document_type = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Patient
        fields = [
            "user",
            "identity_document",
            "document_type",
            "date_birth",
            "phone_number",
            "address",
            "eps",
        ]

    def validate_document_type(self, value: str) -> str:
        if value is None:
            return value

        normalized = value.strip()
        if normalized == "":
            return ""

        mapping = {
            "cc": Patient.DocumentType.CC,
            "ti": Patient.DocumentType.TI,
            "ce": Patient.DocumentType.CE,
            "pasaporte": Patient.DocumentType.PAS,
            "pas": Patient.DocumentType.PAS,
        }
        lowered = normalized.lower()
        if lowered in mapping:
            return mapping[lowered]

        valid = ", ".join([c[0] for c in Patient.DocumentType.choices])
        raise serializers.ValidationError(
            f"Tipo de documento inválido. Usa uno de: {valid}."
        )

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
        patient = Patient.objects.create(user=user, **validated_data)
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
            "eps": instance.eps_id,
        }
