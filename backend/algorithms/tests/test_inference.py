from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
import torch

from algorithms.artifacts import register_weights
from algorithms.inference import analyze_test
from algorithms.models import Algorithm, ModelArtifact, ModelVersion, SectionModelConfig, SectionModelInput, TestSection
from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder
from algorithms.runtimes.torch_inference import ReconstructionResult
from devices.models import DeviceRun, DeviceType, MeasurementBatch, SignalDefinition, SignalTrace, TestDefinition, TestRun


class ZeroReconstructionRuntime:
    """Deterministic test runtime with analytically known window MSE values."""

    algorithm_key = "lstm_ae"
    features = ("temperature", "pressure")

    def __init__(self):
        self.calls = []

    def predict(self, data, *, reconstruction_repeats=10):
        self.calls.append((deepcopy(data), reconstruction_repeats))
        inputs = torch.tensor(data, dtype=torch.float64)
        return ReconstructionResult(torch.zeros_like(inputs), inputs.square().mean(dim=(1, 2)), reconstruction_repeats)


class TestInferenceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        threads = torch.get_num_threads()
        torch.set_num_threads(1)
        cls.addClassCleanup(torch.set_num_threads, threads)

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(username="analysis-test")
        device = DeviceType.objects.create(name="Analysis device")
        cls.definition = TestDefinition.objects.create(name="Test", device_type=device, sample_rate_hz=1000)
        batch = MeasurementBatch.objects.create(recorded_by=user)
        serial = DeviceRun.objects.create(batch=batch, device_type=device, serial_number="ANALYSIS-001")
        cls.test_run = TestRun.objects.create(test=cls.definition, device_run=serial, recorded_by=user)
        for name, samples in (("pressure", [10, 20, 30, 40, 50, 60]), ("temperature", [1, 2, 3, 4, 5, 6])):
            signal = SignalDefinition.objects.create(test=cls.definition, name=name)
            SignalTrace.objects.create(test_run=cls.test_run, signal_definition=signal, samples=samples)

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.version = ModelVersion.objects.create(
            algorithm=Algorithm.objects.get(key="lstm_ae"), version=1,
            architecture_params={"hidden_size": 2, "num_layers": 1, "dropout": 0},
            input_spec={"features": ["temperature", "pressure"], "sample_rate_hz": 1000},
            preprocessing={"schema_version": 1, "steps": [{"type": "window", "size": 2, "tail": "drop"}]},
        )
        with torch.random.fork_rng(devices=[]):
            self.model = LSTMAutoencoder(LSTMArchitecture(2, 1, 0), ("temperature", "pressure"))
        content = BytesIO()
        torch.save(self.model.state_dict(), content)
        self.artifact = register_weights(self.version.pk, ContentFile(content.getvalue()), device_folder="device1")
        self.runtime = ZeroReconstructionRuntime()
        self.section = TestSection.objects.create(
            test=self.definition, name="Section 1", position=0, start_sample=0, end_sample=6,
        )
        self.config = SectionModelConfig.objects.create(
            section=self.section, name="Joint analysis", model_version=self.version,
            threshold=0.35, stride=1, batch_size=2, inference_params={"reconstruction_repeats": 3},
        )
        for feature in self.version.input_spec["features"]:
            SectionModelInput.objects.create(
                config=self.config, feature_name=feature,
                signal=SignalDefinition.objects.get(test=self.definition, name=feature),
            )

    def analyze(self, **options):
        for name, value in options.items():
            if name in ("start_sample", "end_sample"):
                setattr(self.section, name, value)
            elif name == "reconstruction_repeats":
                self.config.inference_params = {"reconstruction_repeats": value}
            else:
                setattr(self.config, name, value)
        self.section.full_clean()
        self.section.save()
        self.config.full_clean()
        self.config.save()
        return analyze_test(self.test_run.pk, self.config.pk)

    def test_selects_feature_order_batches_all_windows_and_returns_plain_scores(self):
        with patch("algorithms.inference.load_model", return_value=self.runtime) as load:
            result = self.analyze()
        load.assert_called_once()
        self.assertEqual([len(data) for data, _ in self.runtime.calls], [2, 2, 1])
        self.assertEqual([count for _, count in self.runtime.calls], [3, 3, 3])
        self.assertEqual(self.runtime.calls[0][0][0], ((1, 10), (2, 20)))
        self.assertEqual(result.features, ("temperature", "pressure"))
        self.assertEqual(result.windows[0].score, 126.25)
        self.assertEqual((result.windows[0].start_sample, result.windows[0].end_sample), (0, 2))
        self.assertEqual((result.windows[-1].start_time_s, result.windows[-1].end_time_s), (0.004, 0.006))
        self.assertTrue(all(type(window.score) is float for window in result.windows))
        self.assertEqual((result.test_run_id, result.model_version_id), (self.test_run.pk, self.version.pk))
        self.assertEqual((result.stride, result.batch_size, result.inference_params), (1, 2, {"reconstruction_repeats": 3}))
        self.assertEqual((result.config_id, result.section_id), (self.config.pk, self.section.pk))
        self.assertEqual(result.signal_ids, tuple(
            SignalDefinition.objects.get(test=self.definition, name=name).pk for name in result.features
        ))
        self.assertEqual(result.threshold, 0.35)
        self.assertTrue(all(window.status == "anomaly" for window in result.windows))

    def test_custom_threshold_includes_equality_in_normal_and_does_not_change_scores(self):
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            result = self.analyze(threshold=328.25)
            higher = self.analyze(threshold=2000)
        self.assertEqual(result.threshold, 328.25)
        self.assertEqual(result.windows[1].score, result.threshold)
        self.assertEqual([window.status for window in result.windows], ["normal", "normal", "anomaly", "anomaly", "anomaly"])
        self.assertTrue(all(window.status == "normal" for window in higher.windows))
        self.assertEqual([window.score for window in result.windows], [window.score for window in higher.windows])

    def test_zero_threshold_accepts_zero_error_and_flags_positive_error(self):
        prediction = SimpleNamespace(scores=torch.tensor([0., 1.]), reconstruction_repeats=3)
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            with patch.object(self.runtime, "predict", return_value=prediction):
                result = self.analyze(threshold=0, end_sample=3)
        self.assertEqual([window.status for window in result.windows], ["normal", "anomaly"])
        self.assertIs(type(result.threshold), float)

    def test_section_bounds_are_absolute_and_windows_do_not_cross_them(self):
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            result = self.analyze(start_sample=1, end_sample=5)
        self.assertEqual([(w.start_sample, w.end_sample) for w in result.windows], [(1, 3), (2, 4), (3, 5)])
        self.assertEqual(self.runtime.calls[0][0][0], ((2, 20), (3, 30)))

    def test_resampling_uses_saved_run_rate_and_keeps_original_time_bounds(self):
        TestDefinition.objects.filter(pk=self.definition.pk).update(sample_rate_hz=2000)
        self.version.input_spec["sample_rate_hz"] = 500
        self.version.preprocessing["steps"].insert(0, {"type": "resample", "method": "mean"})
        self.version.save()
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            result = self.analyze(start_sample=2, end_sample=6)
        self.assertEqual(len(result.windows), 1)
        self.assertEqual(result.source_sample_rate_hz, 1000)
        window = result.windows[0]
        self.assertEqual((window.start_sample, window.end_sample), (2, 6))
        self.assertEqual((window.start_time_s, window.end_time_s), (0.002, 0.006))
        self.assertEqual(self.runtime.calls[0][0][0], ((3.5, 35), (5.5, 55)))

    def test_fitted_normalization_is_applied_without_fitting_or_modifying_records(self):
        self.version.preprocessing["steps"].insert(0, {
            "type": "normalize", "method": "standardize", "mean": [1, 10], "scale": [1, 10],
        })
        self.version.save()
        metadata = ModelVersion.objects.values().get(pk=self.version.pk)
        signals = list(SignalTrace.objects.values())
        run = TestRun.objects.values().get(pk=self.test_run.pk)
        weights = Path(self.artifact.file.path).read_bytes()
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            result = self.analyze()
        self.assertEqual(result.windows[0].score, 0.5)
        self.assertEqual(ModelVersion.objects.values().get(pk=self.version.pk), metadata)
        self.assertEqual(list(SignalTrace.objects.values()), signals)
        self.assertEqual(TestRun.objects.values().get(pk=self.test_run.pk), run)
        self.assertEqual(Path(self.artifact.file.path).read_bytes(), weights)
        self.assertEqual((ModelVersion.objects.count(), ModelArtifact.objects.count()), (1, 1))

    def test_real_checkpoint_to_scores_matches_direct_model_execution(self):
        # Reset the same process-local RNG state for both runs. Model loading
        # preserves it; independent batches intentionally draw fresh LSTM states.
        with patch("algorithms.runtimes.lstm_ae.get_torch_device", return_value=torch.device("cpu")):
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(123)
                result = self.analyze()
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(123)
                expected = []
                for starts in ((0, 1), (2, 3), (4,)):
                    batch = [[(i + 1, (i + 1) * 10) for i in range(start, start + 2)] for start in starts]
                    expected.extend(self.model.predict(batch, reconstruction_repeats=3).scores.tolist())
        self.assertEqual([window.score for window in result.windows], expected)

    def test_incomplete_bindings_are_not_inferred_from_matching_signal_names(self):
        self.config.inputs.filter(feature_name="temperature").delete()
        with patch("algorithms.inference.load_model") as load:
            with self.assertRaisesMessage(ValidationError, "Every model feature must have exactly one explicit signal binding"):
                self.analyze()
            load.assert_not_called()

    def test_empty_unequal_and_nonfinite_signals_fail_before_loading(self):
        trace = SignalTrace.objects.get(test_run=self.test_run, signal_definition__name="temperature")
        for samples in ([], [1, 2], [1, 2, 3, 4, 5, float("nan")]):
            with self.subTest(samples=samples), patch("algorithms.inference.load_model") as load:
                trace.samples = samples
                trace.save()
                with self.assertRaises(ValidationError):
                    self.analyze()
                load.assert_not_called()

    def test_signal_definition_from_another_test_is_rejected(self):
        other = TestDefinition.objects.create(name="Other", device_type=self.definition.device_type, sample_rate_hz=1000)
        self.config.inputs.filter(feature_name="temperature").update(
            signal=SignalDefinition.objects.create(test=other, name="temperature"),
        )
        with self.assertRaisesMessage(ValidationError, "belong to the section's test definition"):
            self.analyze()

    def test_invalid_stored_settings_fail_before_model_loading(self):
        for options in (
            {"stride": 0}, {"batch_size": -1},
            {"reconstruction_repeats": False}, {"reconstruction_repeats": 0},
            {"start_sample": -1},
            {"start_sample": 2, "end_sample": 2},
            {"threshold": -1}, {"threshold": None}, {"threshold": float("nan")},
            {"threshold": float("inf")}, {"threshold": -float("inf")},
        ):
            self.section.refresh_from_db()
            self.config.refresh_from_db()
            with self.subTest(options=options), patch("algorithms.inference.load_model") as load:
                with self.assertRaises(ValidationError):
                    self.analyze(**options)
                load.assert_not_called()

    def test_outside_or_too_short_sample_ranges_fail_before_model_loading(self):
        for options in ({"end_sample": 7}, {"start_sample": 6}, {"start_sample": 5}, {"start_sample": 3, "end_sample": 4}):
            self.section.start_sample, self.section.end_sample = 0, 6
            with self.subTest(options=options), patch("algorithms.inference.load_model") as load:
                with self.assertRaises(ValidationError):
                    self.analyze(**options)
                load.assert_not_called()

    def test_missing_preprocessing_or_unconfigured_rate_conversion_fails_before_loading(self):
        self.version.preprocessing = None
        self.version.save()
        with self.assertRaisesMessage(ValidationError, "preprocessing is not configured"):
            self.analyze()
        self.version.preprocessing = {"schema_version": 1, "steps": [{"type": "window", "size": 2, "tail": "drop"}]}
        self.version.input_spec["sample_rate_hz"] = 500
        self.version.save()
        with self.assertRaisesMessage(ValidationError, "Source and model sample rates differ"):
            self.analyze()

    def test_loading_only_runtime_is_not_treated_as_an_inference_runtime(self):
        runtime = SimpleNamespace(algorithm_key="lstm_ae", features=("temperature", "pressure"))
        with patch("algorithms.inference.load_model", return_value=runtime):
            with self.assertRaisesMessage(ValidationError, "does not support reconstruction-based analysis"):
                self.analyze()

    def test_invalid_scores_or_repeat_metadata_are_rejected(self):
        for scores in (torch.tensor(1.), torch.ones(2, 1), torch.ones(1), torch.tensor([True, False]),
                       torch.tensor([float("nan"), 1]), torch.tensor([-1., 1])):
            prediction = SimpleNamespace(scores=scores, reconstruction_repeats=3)
            with self.subTest(scores=scores), patch("algorithms.inference.load_model", return_value=self.runtime):
                with patch.object(self.runtime, "predict", return_value=prediction):
                    with self.assertRaisesMessage(ValidationError, "one finite, non-negative score per window"):
                        self.analyze()
        prediction = SimpleNamespace(scores=torch.ones(2), reconstruction_repeats=4)
        with patch("algorithms.inference.load_model", return_value=self.runtime), patch.object(self.runtime, "predict", return_value=prediction):
            with self.assertRaisesMessage(ValidationError, "requested reconstruction repeat count"):
                self.analyze()

    def test_missing_database_ids_keep_does_not_exist_errors(self):
        with self.assertRaises(TestRun.DoesNotExist):
            analyze_test(uuid4(), self.config.pk)
        with self.assertRaises(SectionModelConfig.DoesNotExist):
            analyze_test(self.test_run.pk, uuid4())

    def test_signal_renames_do_not_change_explicit_bindings(self):
        SignalDefinition.objects.filter(test=self.definition, name="temperature").update(name="temperature_c")
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            result = self.analyze()
        self.assertEqual(self.runtime.calls[0][0][0], ((1, 10), (2, 20)))
        self.assertEqual(result.features, ("temperature", "pressure"))

    def test_missing_measured_trace_is_rejected_before_loading(self):
        SignalTrace.objects.filter(test_run=self.test_run, signal_definition__name="temperature").delete()
        with patch("algorithms.inference.load_model") as load:
            with self.assertRaisesMessage(ValidationError, "Missing measured signal"):
                self.analyze()
            load.assert_not_called()

    def test_config_cannot_analyze_a_different_test_even_with_matching_device(self):
        other = TestDefinition.objects.create(name="Other", device_type=self.definition.device_type, sample_rate_hz=1000)
        self.section.test = other
        self.section.save()
        with patch("algorithms.inference.load_model") as load:
            with self.assertRaisesMessage(ValidationError, "run must belong to the section's test definition"):
                self.analyze()
            load.assert_not_called()

    def test_sections_have_independent_settings_without_runtime_overrides(self):
        second = TestSection.objects.create(test=self.definition, name="Section 2", position=1, start_sample=2, end_sample=6)
        config = SectionModelConfig.objects.create(
            section=second, name="Another analysis", model_version=self.version,
            threshold=2000, stride=2, batch_size=1, inference_params={"reconstruction_repeats": 1},
        )
        for binding in self.config.inputs.all():
            SectionModelInput.objects.create(config=config, feature_name=binding.feature_name, signal=binding.signal)
        with patch("algorithms.inference.load_model", return_value=self.runtime):
            first = self.analyze()
            result = analyze_test(self.test_run.pk, config.pk)
        self.assertEqual((first.threshold, result.threshold), (0.35, 2000))
        self.assertEqual([(w.start_sample, w.end_sample) for w in result.windows], [(2, 4), (4, 6)])
        self.assertTrue(all(w.status == "normal" for w in result.windows))
        self.assertEqual(result.inference_params, {"reconstruction_repeats": 1})
        self.assertEqual(ModelVersion.objects.count(), 1)
        with self.assertRaises(TypeError):
            analyze_test(self.test_run.pk, config.pk, threshold=0.35)

    def test_mid_inference_edits_do_not_change_the_active_settings_snapshot(self):
        def load_and_edit(version):
            SectionModelConfig.objects.filter(pk=self.config.pk).update(
                threshold=2000, inference_params={"reconstruction_repeats": 1},
            )
            TestSection.objects.filter(pk=self.section.pk).update(start_sample=2)
            return self.runtime

        with patch("algorithms.inference.load_model", side_effect=load_and_edit):
            result = self.analyze()
        self.assertEqual(result.threshold, 0.35)
        self.assertEqual(result.inference_params, {"reconstruction_repeats": 3})
        self.assertEqual(len(result.windows), 5)
        self.assertEqual([repeats for _, repeats in self.runtime.calls], [3, 3, 3])
