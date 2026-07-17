from rest_framework import serializers

from user.serializers import UserResponseSerializer

from .models import Administrative


class AdministrativeStatusSerializer(serializers.ModelSerializer):
    """Read-only minimal representation of an administrative user."""

    user = UserResponseSerializer(read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = Administrative
        fields = [
            "id",
            "identity_document",
            "position",
            "user",
            "is_active",
        ]
