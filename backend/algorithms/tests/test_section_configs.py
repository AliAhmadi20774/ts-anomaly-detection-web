from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from algorithms.models import Algorithm, ModelVersion, SectionModelConfig, SectionModelInput, TestSection
from devices.models import DeviceType, SignalDefinition, TestDefinition


class SectionConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        device = DeviceType.objects.create(name="Device")
        cls.test_definition = TestDefinition.objects.create(name="Test", device_type=device, sample_rate_hz=1000)
        cls.other_test = TestDefinition.objects.create(name="Other", device_type=device, sample_rate_hz=1000)
        cls.current = SignalDefinition.objects.create(test=cls.test_definition, name="current_a")
        cls.voltage = SignalDefinition.objects.create(test=cls.test_definition, name="voltage_v")
        cls.foreign_signal = SignalDefinition.objects.create(test=cls.other_test, name="current_a")
        cls.version = ModelVersion.objects.create(
            algorithm=Algorithm.objects.get(key="lstm_ae"), version=1,
            architecture_params={"hidden_size": 2, "num_layers": 1, "dropout": 0},
            input_spec={"features": ["measurement"]},
            preprocessing={"schema_version": 1, "steps": [{"type": "window", "size": 2, "tail": "drop"}]},
        )
        cls.section = TestSection.objects.create(
            test=cls.test_definition, name="Start", position=0, start_sample=0, end_sample=1000,
        )

    def make_config(self, **overrides):
        return SectionModelConfig(**{
            "section": self.section, "name": "Current analysis", "model_version": self.version,
            "threshold": 0.35, "stride": 25, "batch_size": 100,
            "inference_params": {"reconstruction_repeats": 10}, **overrides,
        })

    def test_sections_inherit_device_from_test_and_allow_overlapping_intervals(self):
        section = TestSection(
            test=self.test_definition, name="Overlap", position=1, start_sample=500, end_sample=1500,
        )
        section.full_clean()
        section.save()
        self.assertEqual(section.test.device_type_id, self.test_definition.device_type_id)
        self.assertEqual(list(self.test_definition.analysis_sections.values_list("name", flat=True)), ["Start", "Overlap"])

    def test_section_bounds_names_and_positions_are_constrained_in_database(self):
        for overrides in (
            {"start_sample": -1}, {"end_sample": 0}, {"start_sample": 10, "end_sample": 10},
            {"name": " "}, {"name": "Start"}, {"position": 0}, {"position": -1},
        ):
            section = TestSection(**{
                "test": self.test_definition, "name": "New", "position": 1,
                "start_sample": 0, "end_sample": 1000, **overrides,
            })
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValidationError):
                    section.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    section.save()

    def test_threshold_and_execution_sizes_have_no_defaults(self):
        for name in ("threshold", "stride", "batch_size", "inference_params"):
            self.assertFalse(SectionModelConfig._meta.get_field(name).has_default())
            with self.subTest(field=name), self.assertRaises(ValidationError):
                self.make_config(**{name: None}).full_clean()

    def test_invalid_thresholds_and_sizes_are_rejected_by_validation_and_database(self):
        for overrides in (
            {"threshold": -1}, {"threshold": float("inf")}, {"threshold": float("-inf")},
            {"threshold": float("nan")}, {"stride": 0}, {"batch_size": 0}, {"name": " "},
            {"inference_params": []}, {"inference_params": "invalid"},
        ):
            with self.subTest(overrides=overrides):
                config = self.make_config(**overrides)
                with self.assertRaises(ValidationError):
                    config.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    config.save()
        config = self.make_config(threshold=0)
        config.full_clean()
        config.save()

    def test_repeat_count_is_explicit_positive_and_algorithm_validated(self):
        for params in ({}, {"reconstruction_repeats": 0}, {"reconstruction_repeats": True},
                       {"reconstruction_repeats": 1.5}, {"reconstruction_repeats": "10"},
                       {"reconstruction_repeats": 10, "unknown": 1}):
            with self.subTest(params=params), self.assertRaises(ValidationError):
                self.make_config(inference_params=params).full_clean()
        config = self.make_config(inference_params={"reconstruction_repeats": 1})
        config.full_clean()
        config.save()
        config.refresh_from_db()
        self.assertEqual(config.inference_params, {"reconstruction_repeats": 1})

    def test_same_section_and_model_can_have_independent_signal_configurations(self):
        for name, signal, threshold in (("Current", self.current, 0.35), ("Voltage", self.voltage, 0.6)):
            config = self.make_config(name=name, threshold=threshold)
            config.full_clean()
            config.save()
            binding = SectionModelInput(config=config, feature_name="measurement", signal=signal)
            binding.full_clean()
            binding.save()
        self.assertEqual(self.version.section_configs.count(), 2)
        self.assertEqual(self.section.model_configs.count(), 2)
        self.assertEqual(ModelVersion.objects.count(), 1)

    def test_config_name_is_unique_within_section(self):
        self.make_config().save()
        duplicate = self.make_config()
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_features_and_signal_test_are_cross_validated(self):
        config = self.make_config()
        config.save()
        for overrides in ({"feature_name": "unknown"}, {"signal": self.foreign_signal}):
            binding = SectionModelInput(**{
                "config": config, "feature_name": "measurement", "signal": self.current, **overrides,
            })
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                binding.full_clean()

    def test_feature_can_only_be_bound_once_and_definition_is_protected(self):
        config = self.make_config()
        config.save()
        SectionModelInput.objects.create(config=config, feature_name="measurement", signal=self.current)
        duplicate = SectionModelInput(config=config, feature_name="measurement", signal=self.voltage)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()
        for instance in (self.current, self.section, self.version, self.test_definition):
            with self.subTest(model=type(instance).__name__), self.assertRaises(ProtectedError):
                instance.delete()
        config.delete()
        self.assertEqual(SectionModelInput.objects.count(), 0)
