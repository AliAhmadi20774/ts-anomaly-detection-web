from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from algorithms.models import Algorithm, ModelVersion


class ModelVersionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.algorithm = Algorithm.objects.get(key="lstm_ae")

    def make_version(self, **overrides):
        return ModelVersion(
            **{
                "algorithm": self.algorithm,
                "version": 1,
                "architecture_params": {"hidden_size": 300, "num_layers": 1, "dropout": 0.2},
                "input_spec": {"features": ["pressure", "temperature"], "sample_rate_hz": 1000},
                **overrides,
            }
        )

    def test_versions_preserve_json_and_feature_order_for_different_architectures(self):
        lstm = self.make_version()
        lstm.full_clean()
        lstm.save()
        transformer = self.make_version(
            algorithm=Algorithm.objects.create(key="example_transformer", name="Example Transformer"),
            architecture_params={"attention_heads": 8, "encoder": {"layers": 3}},
            input_spec={"features": ["temperature", "pressure"]},
        )
        transformer.full_clean()
        transformer.save()
        for model in [lstm, transformer]:
            with self.subTest(algorithm=model.algorithm.key):
                stored = ModelVersion.objects.get(pk=model.pk)
                self.assertIsInstance(stored.pk, UUID)
                self.assertEqual(stored.architecture_params, model.architecture_params)
                self.assertEqual(stored.input_spec, model.input_spec)
        self.assertEqual(str(lstm), "lstm_ae v1")
        self.assertEqual(self.algorithm.model_versions.get(), lstm)

    def test_version_number_is_unique_per_algorithm(self):
        self.make_version().save()
        duplicate = self.make_version()
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()
        next_version = self.make_version(version=2)
        next_version.full_clean()
        next_version.save()

    def test_empty_architecture_object_is_allowed(self):
        model = self.make_version(architecture_params={})
        model.full_clean()
        model.save()
        model.refresh_from_db()
        self.assertEqual(model.architecture_params, {})

    def test_version_number_must_be_positive(self):
        for number in [0, -1]:
            with self.subTest(version=number):
                invalid = self.make_version(version=number)
                with self.assertRaises(ValidationError):
                    invalid.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    invalid.save()

    def test_json_fields_require_objects_in_validation_and_database(self):
        for field in ["architecture_params", "input_spec"]:
            for value in [[], [1], "text", 7, None]:
                with self.subTest(field=field, value=value):
                    invalid = self.make_version(**{field: value})
                    with self.assertRaises(ValidationError):
                        invalid.full_clean()
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        invalid.save()

    def test_input_features_must_be_present_ordered_and_unambiguous(self):
        for value in [{}, {"features": []}, {"features": "pressure"}, {"features": [""]},
                      {"features": ["pressure", "pressure"]}, {"features": [" pressure"]},
                      {"features": [1]}, {"features": ["pressure"], "unknown": 1}]:
            with self.subTest(input_spec=value):
                with self.assertRaises(ValidationError):
                    self.make_version(input_spec=value).full_clean()

    def test_sampling_rate_and_architecture_numbers_must_be_valid(self):
        for rate in [0, -1, True, "1000", None, float("nan"), float("inf"), 10 ** 1000]:
            with self.subTest(rate=rate):
                with self.assertRaises(ValidationError):
                    self.make_version(input_spec={"features": ["pressure"], "sample_rate_hz": rate}).full_clean()
        for value in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(parameter=value):
                with self.assertRaises(ValidationError):
                    self.make_version(architecture_params={"nested": {"parameter": value}}).full_clean()

    def test_algorithm_with_model_versions_cannot_be_deleted(self):
        self.make_version().save()
        with self.assertRaises(ProtectedError):
            self.algorithm.delete()
