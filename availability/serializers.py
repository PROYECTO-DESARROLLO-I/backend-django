from rest_framework import serializers


class SlotSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    duration_minutes = serializers.IntegerField()
    headquarters_id = serializers.IntegerField(allow_null=True)
    headquarters_name = serializers.CharField(allow_null=True)
