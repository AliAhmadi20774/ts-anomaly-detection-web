from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
import torch

from algorithms.artifacts import register_weights
from algorithms.models import Algorithm, ModelArtifact, ModelVersion
from algorithms.preprocessing import iter_preprocessed_windows
from algorithms.runtimes.lstm_ae import LSTMArchitecture, LSTMAutoencoder


class ModelBundleImportTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=str(self.root / "storage"))
        settings.enable()
        self.addCleanup(settings.disable)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.model = {
            "algorithm": "lstm_ae", "version": 1, "device_folder": "device1",
            "weights": "device1/lstm_ae/v1/weights.bin",
            "architecture_params": {"hidden_size": 2, "num_layers": 1, "dropout": 0.2},
            "input_spec": {"features": ["signal1"], "sample_rate_hz": 1000},
            "preprocessing": {"schema_version": 1, "steps": [
                {"type": "resample", "method": "mean"},
                {"type": "normalize", "method": "none"},
                {"type": "window", "size": 2, "tail": "drop"},
            ]},
        }
        self.manifest = {"schema_version": 1, "models": [self.model], "legacy": {"config": {"preserved": True}}}
        self.path = self.bundle / "manifest.json"
        self.source = self.bundle / self.model["weights"]
        self.source.parent.mkdir(parents=True)
        with torch.random.fork_rng(devices=[]):
            model = LSTMAutoencoder(LSTMArchitecture(hidden_size=2, num_layers=1, dropout=0.2), ("signal1",))
        torch.save({"model_state_dict": model.state_dict()}, self.source)

    def run_import(self, *, apply=False):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")
        output = StringIO()
        call_command("import_model_bundle", str(self.path), apply=apply, stdout=output)
        return output.getvalue()

    def create_version(self, **changes):
        fields = {key: self.model[key] for key in ("version", "architecture_params", "input_spec", "preprocessing")}
        return ModelVersion.objects.create(algorithm=Algorithm.objects.get(key="lstm_ae"), **{**fields, **changes})

    def test_preview_validates_real_checkpoint_without_any_writes(self):
        output = self.run_import()
        self.assertIn("Preview only", output)
        self.assertFalse(ModelVersion.objects.exists())
        self.assertFalse(ModelArtifact.objects.exists())
        self.assertFalse((self.root / "storage").exists())

    def test_apply_preserves_bytes_metadata_source_and_is_idempotent(self):
        incoming = self.source.read_bytes()
        self.run_import(apply=True)
        version = ModelVersion.objects.get()
        self.assertEqual(version.preprocessing, self.model["preprocessing"])
        self.assertEqual(version.input_spec, self.model["input_spec"])
        self.assertEqual(version.weights.file.name, self.model["weights"])
        with version.weights.file.open("rb") as stored:
            self.assertEqual(stored.read(), incoming)
        self.assertIn("not active analysis settings", self.run_import(apply=True))
        self.assertEqual(ModelVersion.objects.count(), 1)
        self.assertEqual(ModelArtifact.objects.count(), 1)
        self.assertEqual(self.source.read_bytes(), incoming)
        self.assertEqual(json.loads(self.path.read_text())["legacy"], self.manifest["legacy"])
        windows = list(iter_preprocessed_windows(
            [[1], [2], [3]], preprocessing=version.preprocessing, input_spec=version.input_spec,
            stride=1, source_sample_rate_hz=1000, offset=100,
        ))
        self.assertEqual([(window.start, window.end) for window in windows], [(100, 102), (101, 103)])
        self.assertEqual(windows[0].values, ((1,), (2,)))

    def test_existing_unconfigured_version_is_completed_without_replacing_its_id_or_artifact(self):
        version = self.create_version(preprocessing=None)
        artifact = register_weights(version.pk, ContentFile(self.source.read_bytes()), device_folder="device1")
        self.run_import()
        version.refresh_from_db()
        self.assertIsNone(version.preprocessing)
        self.run_import(apply=True)
        version.refresh_from_db()
        self.assertEqual(version.preprocessing, self.model["preprocessing"])
        self.assertEqual(version.weights_id, artifact.pk)
        self.assertEqual(ModelVersion.objects.get().pk, version.pk)

    def test_conflicting_metadata_never_changes_existing_version(self):
        for key, value in [
            ("architecture_params", {"hidden_size": 3, "num_layers": 1, "dropout": 0.2}),
            ("input_spec", {"features": ["different_signal"], "sample_rate_hz": 1000}),
            ("preprocessing", {"schema_version": 1, "steps": [{"type": "window", "size": 3, "tail": "drop"}]}),
        ]:
            with self.subTest(key=key):
                version = self.create_version(**{key: value})
                with self.assertRaisesMessage(CommandError, f"conflicting {key}"):
                    self.run_import(apply=True)
                version.refresh_from_db()
                self.assertEqual(getattr(version, key), value)
                self.assertFalse(ModelArtifact.objects.exists())
                version.delete()

    def test_different_or_missing_registered_weights_are_not_replaced(self):
        version = self.create_version(preprocessing=None)
        artifact = register_weights(version.pk, ContentFile(b"different weights"), device_folder="device1")
        with self.assertRaisesMessage(CommandError, "conflicting weight file"):
            self.run_import(apply=True)
        Path(artifact.file.path).unlink()
        with self.assertRaises(CommandError):
            self.run_import(apply=True)
        version.refresh_from_db()
        self.assertIsNone(version.preprocessing)
        self.assertFalse(Path(artifact.file.path).exists())

    def test_later_invalid_checkpoint_prevents_all_database_and_storage_writes(self):
        second = deepcopy(self.model)
        second.update(version=2, weights="device1/lstm_ae/v2/weights.bin")
        source = self.bundle / second["weights"]
        source.parent.mkdir(parents=True)
        source.write_bytes(b"not a tensor checkpoint")
        self.manifest["models"].append(second)
        with self.assertRaises(CommandError):
            self.run_import(apply=True)
        self.assertFalse(ModelVersion.objects.exists())
        self.assertFalse(ModelArtifact.objects.exists())
        self.assertFalse((self.root / "storage").exists())

    def test_incompatible_architecture_or_features_fail_before_registration(self):
        for key, value in [
            ("architecture_params", {"hidden_size": 4, "num_layers": 1, "dropout": 0.2}),
            ("input_spec", {"features": ["signal1", "signal2"], "sample_rate_hz": 1000}),
        ]:
            original = self.model[key]
            with self.subTest(key=key), self.assertRaisesMessage(CommandError, "incompatible shape"):
                self.model[key] = value
                self.run_import(apply=True)
            self.model[key] = original
        self.assertFalse(ModelVersion.objects.exists())

    def test_duplicate_versions_and_invalid_envelopes_are_rejected(self):
        original = deepcopy(self.manifest)
        for changes in [
            {"schema_version": True}, {"schema_version": 2}, {"models": []},
            {"models": [self.model, self.model]}, {"unexpected": 1},
        ]:
            with self.subTest(changes=changes), self.assertRaises(CommandError):
                self.manifest = {**original, **changes}
                self.run_import(apply=True)
        self.assertFalse(ModelVersion.objects.exists())

    def test_invalid_paths_unknown_algorithms_and_unconfigured_preprocessing_are_rejected(self):
        original = deepcopy(self.model)
        for changes in [
            {"weights": "../outside.bin"}, {"device_folder": "../escape"},
            {"algorithm": "unknown"}, {"version": True}, {"version": 0},
            {"preprocessing": None}, {"preprocessing": {"schema_version": 1, "steps": [{"type": "normalize", "method": "none"}]}},
        ]:
            with self.subTest(changes=changes), self.assertRaises(CommandError):
                self.manifest["models"] = [{**original, **changes}]
                self.run_import(apply=True)
        self.assertFalse(ModelVersion.objects.exists())
