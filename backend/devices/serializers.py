import math

from rest_framework import serializers

from devices.models import DeviceType, SignalDefinition, TestDefinition, TestRun


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


class TestRunSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    device_type_name = serializers.CharField(source="device_type.name", read_only=True)
    recorded_by_code = serializers.CharField(source="recorded_by.username", read_only=True)

    class Meta:
        model = TestRun
        fields = (
            "id", "test", "test_name", "device_serial_number", "device_type", "device_type_name",
            "sample_rate_hz", "executed_at", "recorded_by", "recorded_by_code", "created_at", "notes",
            "flat_result_data",
        )
        read_only_fields = ("id", "device_type", "sample_rate_hz", "recorded_by", "created_at")

    def validate_test(self, value: TestDefinition) -> TestDefinition:
        if self.instance and self.instance.test_id != value.pk:
            raise serializers.ValidationError("The test definition cannot be changed after recording a run.")

        return value


class TestRunListSerializer(TestRunSerializer):
    class Meta(TestRunSerializer.Meta):
        fields = tuple(field for field in TestRunSerializer.Meta.fields if field != "flat_result_data")
