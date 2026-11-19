from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from devices.models import DeviceType, SignalDefinition, TestDefinition


class DefinitionTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.device = DeviceType.objects.create(name="device1")
        cls.test = TestDefinition.objects.create(
            name="test1", device_type=cls.device, sample_rate_hz=1000
        )

    def test_names_can_repeat_under_different_parents(self) -> None:
        second_device = DeviceType.objects.create(name="device2")
        second_test = TestDefinition.objects.create(
            name="test1", device_type=second_device, sample_rate_hz=12.5
        )
        first_signal = SignalDefinition.objects.create(name="signal1", test=self.test)
        second_signal = SignalDefinition.objects.create(name="signal1", test=second_test)

        self.assertEqual(first_signal.test.device_type, self.device)
        self.assertEqual(second_signal.test.device_type, second_device)
        self.assertNotEqual(first_signal.id, second_signal.id)
        self.assertEqual(self.device.tests.get(), self.test)
        self.assertEqual(second_test.signals.get(), second_signal)
        self.assertEqual(second_test.sample_rate_hz, 12.5)

    def test_database_rejects_wrong_parent_identifiers(self) -> None:
        invalid_objects = [
            TestDefinition(
                name="invalid", device_type_id=self.test.id, sample_rate_hz=1000
            ),
            SignalDefinition(name="invalid", test_id=self.device.id),
        ]
        for definition in invalid_objects:
            with self.subTest(model=type(definition).__name__):
                with self.assertRaises(ValidationError):
                    definition.full_clean()
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        definition.save()
                        connection.check_constraints()

    def test_sample_rate_must_be_positive_and_finite(self) -> None:
        for rate in (0, -1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(rate=rate):
                definition = TestDefinition(
                    name="invalid", device_type=self.device, sample_rate_hz=rate
                )
                with self.assertRaises(ValidationError):
                    definition.full_clean()
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        definition.save()

    def test_blank_names_are_rejected(self) -> None:
        definitions = [
            DeviceType(name=" "),
            TestDefinition(name=" ", device_type=self.device, sample_rate_hz=1000),
            SignalDefinition(name=" ", test=self.test),
        ]
        for definition in definitions:
            with self.subTest(model=type(definition).__name__):
                with self.assertRaises(ValidationError):
                    definition.full_clean()
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        definition.save()

    def test_parent_with_children_cannot_be_deleted(self) -> None:
        SignalDefinition.objects.create(name="signal1", test=self.test)

        with self.assertRaises(ProtectedError):
            self.device.delete()
        with self.assertRaises(ProtectedError):
            self.test.delete()
