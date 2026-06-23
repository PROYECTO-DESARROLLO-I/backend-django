from rest_framework import serializers
from .models import Headquarters

class HeadquartersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Headquarters
        fields = ["id", "name", "address", "phone", "active"]