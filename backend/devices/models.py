from uuid import uuid4

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThan
from django.utils import timezone

from devices.validators import FlatResultDataValidator


class DeviceType(models.Model):
    """Define a device type independently of individual serial numbers."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.TextField(validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")])

    class Meta:
        db_table = "device_types"
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("name")), 0),
                name="device_types_name_check",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class TestDefinition(models.Model):
    """Define a test and its sample rate for one device type."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.TextField(validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")])
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name="tests")
    sample_rate_hz = models.FloatField(help_text="Samples per second (Hz).")

    class Meta:
        db_table = "test_definitions"
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("name")), 0),
                name="test_definitions_name_check",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(sample_rate_hz__gt=0)
                    & models.Q(sample_rate_hz__lt=float("inf"))
                ),
                name="test_definitions_sample_rate_valid",
            ),
            models.UniqueConstraint(
                fields=["device_type", "name"],
                name="test_definitions_device_type_name_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.device_type} / {self.name}"


class SignalDefinition(models.Model):
    """Define a signal within a test, separately from measured values."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.TextField(validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")])
    test = models.ForeignKey(TestDefinition, on_delete=models.PROTECT, related_name="signals")

    class Meta:
        db_table = "signal_definitions"
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("name")), 0),
                name="signal_definitions_name_check",
            ),
            models.UniqueConstraint(
                fields=["test", "name"],
                name="signal_definitions_test_name_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class MeasurementBatch(models.Model):
    """One received set of measurements, potentially from several DAT files."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="measurement_batches",
    )

    class Meta:
        db_table = "measurement_batches"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.id} / {self.created_at}"


class DeviceRun(models.Model):
    """One device serial number within a measurement batch."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    batch = models.ForeignKey(MeasurementBatch, on_delete=models.PROTECT, related_name="devices")
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name="device_runs")
    serial_number = models.CharField(max_length=128, validators=[RegexValidator(r"\S", "Enter a device serial number.")])

    class Meta:
        db_table = "device_runs"
        ordering = ["serial_number", "id"]
        constraints = [
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("serial_number")), 0),
                name="device_runs_serial_not_blank",
            ),
            models.UniqueConstraint(
                fields=["batch", "device_type", "serial_number"],
                name="device_runs_batch_type_serial_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.device_type} / {self.serial_number}"


class TestRun(models.Model):
    """Record one execution, preserving its device type and sampling rate."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    test = models.ForeignKey(TestDefinition, on_delete=models.PROTECT, related_name="runs")
    device_run = models.ForeignKey(DeviceRun, on_delete=models.PROTECT, related_name="test_runs")
    device_serial_number = models.CharField(max_length=128, validators=[RegexValidator(r"\S", "Enter a device serial number.")])

    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name="runs", editable=False)
    sample_rate_hz = models.FloatField(editable=False)

    executed_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="test_runs")
    flat_result_data = models.JSONField(null=True, blank=True, validators=[FlatResultDataValidator()])
    source_file_name = models.CharField(max_length=255, blank=True)
    source_file_sha256 = models.CharField(max_length=64, blank=True)
    source_device_index = models.PositiveIntegerField(null=True, blank=True)
    source_test_index = models.PositiveIntegerField(null=True, blank=True)
    source_operator_name = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "test_runs"
        ordering = ["-executed_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=GreaterThan(Length(Trim("device_serial_number")), 0),
                name="test_runs_serial_not_blank",
            ),
            models.CheckConstraint(
                condition=(models.Q(sample_rate_hz__gt=0) & models.Q(sample_rate_hz__lt=float("inf"))),
                name="test_runs_sample_rate_valid",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        if self._state.adding:
            self.device_type = self.device_run.device_type
            self.device_serial_number = self.device_run.serial_number
            self.sample_rate_hz = self.test.sample_rate_hz

        super().save(*args, **kwargs)

    @property
    def created_at(self):
        return self.device_run.batch.created_at

    def __str__(self) -> str:
        return f"{self.device_serial_number} / {self.test.name} / {self.executed_at}"


class SignalTrace(models.Model):
    """Store all measured samples for one signal in a test run."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="signal_traces")
    signal_definition = models.ForeignKey(SignalDefinition, on_delete=models.PROTECT, related_name="traces")
    samples = ArrayField(models.FloatField())

    class Meta:
        db_table = "signal_traces"
        ordering = ["signal_definition__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["test_run", "signal_definition"],
                name="signal_traces_run_definition_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.test_run} / {self.signal_definition.name}"
