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
from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder


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
        with self.assertRaisesMessage(ValidationError, "only the lstm_ae"):
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
            with self.subTest(size=len(content)), patch("algorithms.loading.load_lstm_ae") as deserialize:
                with self.assertRaisesMessage(ValidationError, "file size differs"):
                    load_model_version(self.version.pk)
                deserialize.assert_not_called()

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
        self.assertIn("weights loaded on CPU", output.getvalue())
        self.assertIn("2 feature(s)", output.getvalue())

    def test_check_command_reports_missing_version_and_invalid_weights(self):
        with self.assertRaisesMessage(CommandError, "Model version does not exist"):
            call_command("check_model_weights", str(uuid4()), stdout=StringIO())
        self.register(b"not a checkpoint")
        with self.assertRaisesMessage(CommandError, "supported tensor checkpoint"):
            call_command("check_model_weights", str(self.version.pk), stdout=StringIO())
