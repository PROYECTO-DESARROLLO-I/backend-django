from secrets import SystemRandom

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.crypto import get_random_string

from user.models import User
from patient.models import Patient
from eps.models import EPS
from administrative.models import Administrative
from doctor.models import Doctor
from headquarters.models import Headquarters
from specialties.models import Specialty


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


class InternalStaffRegisterSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    rol = serializers.ChoiceField(
        choices=(
            (User.Role.DOCTOR, "Médico"),
            (User.Role.ADMINISTRATIVE, "Administrativo"),
        ),
    )
    identity_document = serializers.CharField(max_length=50)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    generate_temporary_password = serializers.BooleanField(
        required=False,
        default=False,
    )

    # Datos específicos de médico
    specialties = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Specialty.objects.filter(active=True),
        required=False,
        write_only=True,
    )
    register_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
    )
    academic_information = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
    )

    # Datos específicos de administrativo
    headquarters = serializers.PrimaryKeyRelatedField(
        queryset=Headquarters.objects.filter(active=True),
        required=False,
        allow_null=True,
    )
    position = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_email(self, value):
        normalized_email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta registrada con este correo electrónico."
            )
        return normalized_email

    def validate_identity_document(self, value):
        if Patient.objects.filter(identity_document=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario registrado con este número de documento."
            )
        if Doctor.objects.filter(identity_document=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario registrado con este número de documento."
            )
        if Administrative.objects.filter(identity_document=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario registrado con este número de documento."
            )
        return value

    def validate_register_number(self, value):
        if Doctor.objects.filter(register_number=value).exists():
            raise serializers.ValidationError(
                "Ya existe un médico registrado con este registro médico."
            )
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        generate_temporary_password = attrs.get("generate_temporary_password", False)

        if not password and not generate_temporary_password:
            raise serializers.ValidationError(
                {
                    "password": (
                        "Debe asignar una contraseña inicial manualmente o "
                        "solicitar la generación de una contraseña temporal."
                    )
                }
            )

        if password and generate_temporary_password:
            raise serializers.ValidationError(
                {
                    "password": (
                        "No puede asignar una contraseña manual y generar una "
                        "contraseña temporal al mismo tiempo."
                    )
                }
            )

        if password:
            validate_password(password)

        if attrs["rol"] == User.Role.DOCTOR:
            missing_fields = {}
            if not attrs.get("specialties"):
                missing_fields["specialties"] = "La especialidad médica es obligatoria."
            if not attrs.get("register_number"):
                missing_fields["register_number"] = "El registro médico es obligatorio."
            if missing_fields:
                raise serializers.ValidationError(missing_fields)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        specialties = validated_data.pop("specialties", [])
        headquarters = validated_data.pop("headquarters", None)
        position = validated_data.pop("position", "")
        register_number = validated_data.pop("register_number", None)
        academic_information = validated_data.pop("academic_information", "")
        phone_number = validated_data.pop("phone_number", "")
        generate_temporary_password = validated_data.pop(
            "generate_temporary_password",
            False,
        )
        password = validated_data.pop("password", None)
        temporary_password = None

        if generate_temporary_password:
            password_chars = list(
                get_random_string(4, allowed_chars="abcdefghijkmnopqrstuvwxyz")
                + get_random_string(4, allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ")
                + get_random_string(4, allowed_chars="23456789")
                + get_random_string(4, allowed_chars="!@#$%&*")
            )
            SystemRandom().shuffle(password_chars)
            temporary_password = "".join(password_chars)
            password = temporary_password

        role = validated_data["rol"]
        identity_document = validated_data.pop("identity_document")
        user = User.objects.create_user(password=password, **validated_data)

        profile = None
        if role == User.Role.DOCTOR:
            profile = Doctor.objects.create(
                user=user,
                identity_document=identity_document,
                register_number=register_number,
                academic_information=academic_information,
                phone_number=phone_number,
            )
            profile.specialties.set(specialties)
        elif role == User.Role.ADMINISTRATIVE:
            profile = Administrative.objects.create(
                user=user,
                identity_document=identity_document,
                headquarters=headquarters,
                position=position,
            )

        user._created_profile = profile
        user._temporary_password = temporary_password
        return user

    def to_representation(self, instance):
        profile = getattr(instance, "_created_profile", None)
        data = {
            "id": instance.id,
            "email": instance.email,
            "nombre": instance.nombre,
            "apellido": instance.apellido,
            "rol": instance.rol,
            "profile_id": profile.id if profile else None,
        }

        temporary_password = getattr(instance, "_temporary_password", None)
        if temporary_password:
            data["temporary_password"] = temporary_password

        return data
