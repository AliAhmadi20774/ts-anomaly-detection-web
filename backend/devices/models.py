from uuid import uuid4

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThan


class DeviceType(models.Model):
    """Define a device type independently of individual serial numbers."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.TextField(
        validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")]
    )

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
    name = models.TextField(
        validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")]
    )
    device_type = models.ForeignKey(
        DeviceType, on_delete=models.PROTECT, related_name="tests"
    )
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
    name = models.TextField(
        validators=[RegexValidator(r"\S", "Name must contain a non-whitespace character.")]
    )
    test = models.ForeignKey(
        TestDefinition, on_delete=models.PROTECT, related_name="signals"
    )

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
