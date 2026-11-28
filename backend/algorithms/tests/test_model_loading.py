from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import torch
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from algorithms.artifacts import register_weights
from algorithms.loading import load_model_version
from algorithms.models import Algorithm, ModelArtifact, ModelVersion
from algorithms.runtimes.contracts import ModelRuntime
from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder


@dataclass(frozen=True)
class ExampleRuntime:
    algorithm_key: str
    features: tuple[str, ...]


class ModelLoadingTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.version = ModelVersion.objects.create(
            algorithm=Algorithm.objects.get(key="lstm_ae"), version=1,
            architecture_params={"hidden_size": 2, "num_layers": 1, "dropout": 0.2},
            input_spec={"features": ["pressure", "temperature"], "sample_rate_hz": 1000},
        )
        self.original = LSTMAutoencoder(LSTMArchitecture(2, 1, 0.2), ("pressure", "temperature"))
        stream = BytesIO()
        torch.save({"model_state_dict": self.original.state_dict(), "epoch": 1}, stream)
        self.content = stream.getvalue()

    def register(self, content=None):
        return register_weights(
            self.version.pk, ContentFile(self.content if content is None else content), device_folder="device1",
        )

    def test_registered_weights_load_without_changing_database_or_file(self):
        artifact = self.register()
        metadata = ModelVersion.objects.values().get(pk=self.version.pk)
        model = load_model_version(self.version.pk)
        self.assertIsInstance(model, ModelRuntime)
        self.assertEqual(model.algorithm_key, "lstm_ae")
        for name, tensor in model.state_dict().items():
            torch.testing.assert_close(tensor, self.original.state_dict()[name], rtol=0, atol=0)
        self.assertEqual(model.features, ("pressure", "temperature"))
        self.assertFalse(model.training)
        self.assertIsNone(metadata["preprocessing"])
        self.assertEqual(ModelVersion.objects.values().get(pk=self.version.pk), metadata)
        self.assertEqual(ModelArtifact.objects.count(), 1)
        self.assertEqual(Path(artifact.file.path).read_bytes(), self.content)

    def test_missing_version_and_missing_registration_are_reported(self):
        with self.assertRaises(ModelVersion.DoesNotExist):
            load_model_version(uuid4())
        with self.assertRaisesMessage(ValidationError, "no registered weights"):
            load_model_version(self.version.pk)

    def test_other_algorithms_are_not_loaded_as_lstm(self):
        self.version.algorithm = Algorithm.objects.create(key="transad", name="TransAD")
        self.version.save(update_fields=["algorithm"])
        with self.assertRaisesMessage(ValidationError, "No model loader is available for algorithm 'transad'"):
            load_model_version(self.version.pk)

    def test_missing_stored_file_has_an_actionable_error(self):
        artifact = self.register()
        Path(artifact.file.path).unlink()
        with self.assertRaisesMessage(ValidationError, "weights are unavailable"):
            load_model_version(self.version.pk)

    def test_truncated_or_enlarged_files_fail_before_deserialization(self):
        artifact = self.register()
        for content in (self.content[:-10], self.content + b"extra"):
            Path(artifact.file.path).write_bytes(content)
            with self.subTest(size=len(content)), patch("algorithms.loading.get_model_loader") as resolve:
                with self.assertRaisesMessage(ValidationError, "file size differs"):
                    load_model_version(self.version.pk)
                resolve.return_value.assert_not_called()

    def test_corrupt_checkpoint_errors_are_exposed_as_validation_errors(self):
        self.register(b"not a checkpoint")
        with self.assertRaisesMessage(ValidationError, "supported tensor checkpoint"):
            load_model_version(self.version.pk)

    def test_registered_architecture_mismatch_is_rejected(self):
        self.register()
        self.version.architecture_params = {"hidden_size": 3, "num_layers": 1, "dropout": 0.2}
        self.version.save(update_fields=["architecture_params"])
        with self.assertRaisesMessage(ValidationError, "incompatible shape"):
            load_model_version(self.version.pk)

    def test_loading_uses_storage_streams_without_requiring_a_local_path(self):
        self.register()
        with (
            patch("django.core.files.storage.default_storage.open", return_value=BytesIO(self.content)) as open_file,
            patch("django.core.files.storage.default_storage.path", side_effect=AssertionError("Local path requested")),
        ):
            model = load_model_version(self.version.pk)
        open_file.assert_called_once_with("device1/lstm_ae/v1/weights.bin", "rb")
        self.assertFalse(model.training)

    def test_check_command_reports_success_without_running_inference(self):
        self.register()
        output = StringIO()
        call_command("check_model_weights", str(self.version.pk), stdout=output)
        self.assertIn("weights loaded for lstm_ae", output.getvalue())
        self.assertIn("2 feature(s)", output.getvalue())

    def test_check_command_reports_missing_version_and_invalid_weights(self):
        with self.assertRaisesMessage(CommandError, "Model version does not exist"):
            call_command("check_model_weights", str(uuid4()), stdout=StringIO())
        self.register(b"not a checkpoint")
        with self.assertRaisesMessage(CommandError, "supported tensor checkpoint"):
            call_command("check_model_weights", str(self.version.pk), stdout=StringIO())

    def test_another_algorithm_uses_the_same_database_and_storage_loading_path(self):
        self.version.algorithm = Algorithm.objects.create(key="example_detector", name="Example Detector")
        self.version.architecture_params = {"custom_parameter": 7}
        self.version.save(update_fields=["algorithm", "architecture_params"])
        self.register(b"external trained weights")
        received = {}

        def load_example(source, *, architecture_params, input_spec):
            received.update(content=source.read(), architecture_params=architecture_params, input_spec=input_spec)
            return ExampleRuntime("example_detector", tuple(input_spec["features"]))

        with patch("algorithms.loading.get_model_loader", return_value=load_example) as resolve:
            runtime = load_model_version(self.version.pk)
        resolve.assert_called_once_with("example_detector")
        self.assertEqual(runtime, ExampleRuntime("example_detector", ("pressure", "temperature")))
        self.assertEqual(received, {
            "content": b"external trained weights", "architecture_params": {"custom_parameter": 7},
            "input_spec": self.version.input_spec,
        })

    def test_loader_results_must_match_the_shared_contract_and_version_identity(self):
        self.register()
        cases = (
            (object(), "return a ModelRuntime"),
            (ExampleRuntime("wrong_algorithm", ("pressure", "temperature")), "algorithm does not match"),
            (ExampleRuntime("lstm_ae", ("temperature", "pressure")), "features do not match"),
        )
        for result, message in cases:
            def load_example(source, *, architecture_params, input_spec):
                return result

            with (
                self.subTest(result=result),
                patch("algorithms.loading.get_model_loader", return_value=load_example),
                self.assertRaisesMessage(ValidationError, message),
            ):
                load_model_version(self.version.pk)

    def test_loader_cannot_change_the_expected_feature_order(self):
        self.register()

        def load_reordered(source, *, architecture_params, input_spec):
            input_spec["features"].reverse()
            return ExampleRuntime("lstm_ae", tuple(input_spec["features"]))

        with (
            patch("algorithms.loading.get_model_loader", return_value=load_reordered),
            self.assertRaisesMessage(ValidationError, "features do not match"),
        ):
            load_model_version(self.version.pk)

    def test_generic_command_supports_a_runtime_without_lstm_attributes(self):
        runtime = ExampleRuntime("example_detector", ("pressure",))
        output = StringIO()
        with patch("algorithms.management.commands.check_model_weights.load_model_version", return_value=runtime):
            call_command("check_model_weights", str(self.version.pk), stdout=output)
        self.assertEqual(output.getvalue().strip(), "Model weights loaded for example_detector: 1 feature(s).")
