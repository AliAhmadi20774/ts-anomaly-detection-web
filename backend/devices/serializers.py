import math

from rest_framework import serializers

from devices.models import DeviceType, SignalDefinition, TestDefinition


class DeviceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceType
        fields = ("id", "name")
        read_only_fields = ("id",)


class TestDefinitionSerializer(serializers.ModelSerializer):
    device_type_name = serializers.CharField(source="device_type.name", read_only=True)

    class Meta:
        model = TestDefinition
        fields = ("id", "name", "device_type", "device_type_name", "sample_rate_hz")
        read_only_fields = ("id",)

    def validate_sample_rate_hz(self, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise serializers.ValidationError(
                "Sample rate must be a finite number greater than zero."
            )
        return value


class SignalDefinitionSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    device_type_name = serializers.CharField(source="test.device_type.name", read_only=True)

    class Meta:
        model = SignalDefinition
        fields = ("id", "name", "test", "test_name", "device_type_name")
        read_only_fields = ("id",)
