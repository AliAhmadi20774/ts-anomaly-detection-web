from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from algorithms.models import Algorithm


class AlgorithmTests(TestCase):
    def test_migration_registers_the_legacy_algorithm(self):
        algorithm = Algorithm.objects.get(key="lstm_ae")
        self.assertIsInstance(algorithm.pk, UUID)
        self.assertEqual(algorithm.name, "LSTM Autoencoder")
        self.assertEqual(str(algorithm), "LSTM Autoencoder")
        self.assertEqual(Algorithm.objects.count(), 1)

    def test_key_is_unique_in_validation_and_database(self):
        duplicate = Algorithm(key="lstm_ae", name="Another name")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_key_format_is_enforced_in_validation_and_database(self):
        for key in ["", "LSTM_AE", "lstm ae", "lstm-ae", "1lstm", "lstm_ae\n"]:
            with self.subTest(key=key):
                invalid = Algorithm(key=key, name="Algorithm")
                with self.assertRaises(ValidationError):
                    invalid.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    invalid.save()

    def test_name_cannot_be_only_whitespace(self):
        for name in ["", "   ", "\t\n"]:
            with self.subTest(name=name):
                invalid = Algorithm(key="example", name=name)
                with self.assertRaises(ValidationError):
                    invalid.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    invalid.save()

    def test_display_name_can_change_while_the_key_is_preserved(self):
        algorithm = Algorithm.objects.get(key="lstm_ae")
        identifier = algorithm.pk
        algorithm.name = "اتوانکودر LSTM"
        algorithm.full_clean()
        algorithm.save(update_fields=["name"])
        algorithm.refresh_from_db()
        self.assertEqual(algorithm.pk, identifier)
        self.assertEqual(algorithm.key, "lstm_ae")
        self.assertEqual(algorithm.name, "اتوانکودر LSTM")
