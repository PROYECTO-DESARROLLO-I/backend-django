from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from doctor.models import Doctor, DoctorSpecialty
from specialties.models import Specialty
from user.models import User


class DoctorCreateSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    identity_document = serializers.CharField(max_length=50)
    register_number = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    academic_information = serializers.CharField(required=False, allow_blank=True, default="")
    specialty_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        error_messages={"min_length": "Debe seleccionar al menos una especialidad."},
    )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return value

    def validate_identity_document(self, value):
        if Doctor.objects.filter(identity_document=value).exists():
            raise serializers.ValidationError("Ya existe un médico con este número de documento.")
        return value

    def validate_register_number(self, value):
        if Doctor.objects.filter(register_number=value).exists():
            raise serializers.ValidationError("Ya existe un médico con este número de registro médico.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_specialty_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        found = list(Specialty.objects.filter(pk__in=unique_ids, active=True))
        if len(found) != len(unique_ids):
            raise serializers.ValidationError("Una o más especialidades no existen o no están activas.")
        return unique_ids

    @transaction.atomic
    def create(self, validated_data):
        specialty_ids = validated_data.pop("specialty_ids")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            nombre=validated_data["nombre"],
            apellido=validated_data["apellido"],
            rol=User.Role.DOCTOR,
        )

        doctor = Doctor.objects.create(
            user=user,
            identity_document=validated_data["identity_document"],
            register_number=validated_data["register_number"],
            phone_number=validated_data.get("phone_number", ""),
            academic_information=validated_data.get("academic_information", ""),
        )

        specialties = Specialty.objects.filter(pk__in=specialty_ids, active=True)
        for specialty in specialties:
            DoctorSpecialty.objects.create(doctor=doctor, specialty=specialty)

        return doctor


class DoctorDetailSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="user.nombre")
    apellido = serializers.CharField(source="user.apellido")
    email = serializers.EmailField(source="user.email")
    specialties = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            "id",
            "nombre",
            "apellido",
            "email",
            "identity_document",
            "register_number",
            "phone_number",
            "academic_information",
            "specialties",
            "active",
        ]

    def get_specialties(self, obj):
        return list(obj.specialties.values("id", "name"))


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
