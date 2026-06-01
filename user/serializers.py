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
