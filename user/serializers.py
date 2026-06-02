from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from user.models import User
from patient.models import Patient
from eps.models import EPS


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )
    password = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=False,
        write_only=True,
    )

class PatientRegisterSerializer(serializers.Serializer):
    #Datos del user
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    #username = serializers.CharField(max_length=150) //con razon no me funcionaba si no estamos usando esto en el user model xd
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )

    #Datos del patient
    identity_document = serializers.CharField(max_length=20)
    document_type = serializers.ChoiceField(
        choices= Patient.DocumentType.choices  #Usa las choices definidas en el modelo patient
    )
    date_birth = serializers.DateField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    eps = serializers.PrimaryKeyRelatedField(
        queryset=EPS.objects.filter(active=True),
        required=False,
        allow_null=True
    )

    #Validaciones para campos

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta registrada con este correo electrónico."
            )
        return value

    def validate_identity_document(self, value):
        if Patient.objects.filter(identity_document=value).exists():
            raise serializers.ValidationError(
                "Ya existe un paciente registrado con este número de documento."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value
    
    """ No es necesario validar esto porque no estamos usando username en el modelo User, pero lo dejo comentado por si acaso xd
    def validate(self, data):
        #El nombre de usuario no puede ser igual a la contraseña
        if data.get('username') == data.get('password'):
            raise serializers.ValidationError(
                {"password": "La contraseña no puede ser igual al nombre de usuario."}
            )
        return data
    """

    #Crear el user y el patient de forma atómica para evitar errores en la BDD

    @transaction.atomic
    def create(self, validated_data):
        # Separar datos de Patient
        patient_fields = ['identity_document', 'document_type',
                          'date_birth', 'phone_number', 'address', 'eps']
        patient_data = {
            field: validated_data.pop(field, None)
            for field in patient_fields
        }

        #Crea el User con rol paciente
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            nombre=validated_data['nombre'],
            apellido=validated_data['apellido'],
            rol='paciente',
        )

        #Crea el Paciente vinculado al User
        Patient.objects.create(
            user=user,
            **{k: v for k, v in patient_data.items() if v is not None}
        )

        return user