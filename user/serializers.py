<<<<<<< HEAD
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSignupSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "nombre", "apellido", "rol"]
=======
from rest_framework import serializers


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
>>>>>>> feature/login
