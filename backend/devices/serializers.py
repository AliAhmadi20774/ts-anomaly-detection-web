import math

from rest_framework import serializers

from devices.models import DeviceRun, DeviceType, MeasurementBatch, SignalDefinition, TestDefinition, TestRun


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
    created_at = serializers.DateTimeField(source="device_run.batch.created_at", read_only=True)
    measurement_batch = serializers.UUIDField(source="device_run.batch_id", read_only=True)

    class Meta:
        model = TestRun
        fields = (
            "id", "test", "test_name", "device_run", "measurement_batch", "device_serial_number",
            "device_type", "device_type_name", "sample_rate_hz", "executed_at", "recorded_by",
            "recorded_by_code", "created_at",
            "flat_result_data", "source_file_name", "source_operator_name",
        )
        read_only_fields = (
            "id", "device_run", "measurement_batch", "device_type", "sample_rate_hz", "recorded_by", "created_at",
            "source_file_name", "source_operator_name",
        )

    def validate_test(self, value: TestDefinition) -> TestDefinition:
        if self.instance and self.instance.test_id != value.pk:
            raise serializers.ValidationError("The test definition cannot be changed after recording a run.")

        return value

    def validate_device_serial_number(self, value: str) -> str:
        if self.instance and value != self.instance.device_serial_number:
            if self.instance.source_file_sha256 or self.instance.device_run.test_runs.exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("The serial number of an imported or shared device run cannot be changed.")
        return value

    def update(self, instance: TestRun, validated_data: dict) -> TestRun:
        serial_number = validated_data.get("device_serial_number")
        if serial_number and serial_number != instance.device_serial_number:
            from django.db import transaction

            with transaction.atomic():
                instance.device_run.serial_number = serial_number
                instance.device_run.save(update_fields=["serial_number"])
                return super().update(instance, validated_data)
        return super().update(instance, validated_data)


class TestRunListSerializer(TestRunSerializer):
    class Meta(TestRunSerializer.Meta):
        fields = tuple(field for field in TestRunSerializer.Meta.fields if field != "flat_result_data")


class BatchTestRunSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)

    class Meta:
        model = TestRun
        fields = ("id", "test", "test_name", "executed_at", "sample_rate_hz")


class DeviceRunSerializer(serializers.ModelSerializer):
    device_type_name = serializers.CharField(source="device_type.name", read_only=True)
    tests = BatchTestRunSerializer(source="test_runs", many=True, read_only=True)

    class Meta:
        model = DeviceRun
        fields = ("id", "device_type", "device_type_name", "serial_number", "tests")


class MeasurementBatchSerializer(serializers.ModelSerializer):
    recorded_by_code = serializers.CharField(source="recorded_by.username", read_only=True)
    devices = DeviceRunSerializer(many=True, read_only=True)

    class Meta:
        model = MeasurementBatch
        fields = ("id", "created_at", "recorded_by_code", "devices")
