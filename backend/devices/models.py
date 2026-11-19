from uuid import uuid4

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
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
        ]

    def __str__(self) -> str:
        return self.name


class TestRun(models.Model):
    """Record one execution, preserving its device type and sampling rate."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    test = models.ForeignKey(TestDefinition, on_delete=models.PROTECT, related_name="runs")
    device_serial_number = models.CharField(max_length=128, validators=[RegexValidator(r"\S", "Enter a device serial number.")])

    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name="runs", editable=False)
    sample_rate_hz = models.FloatField(editable=False)

    executed_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="test_runs")
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    flat_result_data = models.JSONField(null=True, blank=True, validators=[FlatResultDataValidator()])

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
            self.device_type = self.test.device_type
            self.sample_rate_hz = self.test.sample_rate_hz

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.device_serial_number} / {self.test.name} / {self.executed_at}"
