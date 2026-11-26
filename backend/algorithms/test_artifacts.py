from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings

from algorithms.artifacts import register_weights
from algorithms.models import Algorithm, ModelArtifact, ModelVersion
from devices.models import DeviceType


class ModelArtifactTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.version = ModelVersion.objects.create(
            algorithm=Algorithm.objects.get(key="lstm_ae"), version=1,
            device_type=DeviceType.objects.create(name="device1"),
            architecture_params={"hidden_size": 300, "num_layers": 1, "dropout": 0.2},
            input_spec={"features": ["signal1"], "sample_rate_hz": 1000},
        )
        self.content = b"example checkpoint bytes"

    def register(self, version=None, content=None):
        return register_weights(
            (version or self.version).pk,
            ContentFile(self.content if content is None else content, name="../../original checkpoint"),
        )

    def test_register_stores_exact_bytes_metadata_and_version_link(self):
        artifact = self.register()
        self.version.refresh_from_db()
        self.assertEqual(self.version.weights, artifact)
        self.assertEqual(artifact.size_bytes, len(self.content))
        self.assertTrue(Path(artifact.file.path).is_relative_to(self.root))
        self.assertNotIn("original checkpoint", artifact.file.name)
        with artifact.file.open("rb") as stored:
            self.assertEqual(stored.read(), self.content)

    def test_registration_is_idempotent_but_versions_have_separate_files(self):
        first = self.register()
        self.assertEqual(self.register().pk, first.pk)
        other = ModelVersion.objects.create(
            algorithm=self.version.algorithm, version=2,
            device_type=self.version.device_type,
            architecture_params={}, input_spec={"features": ["signal1"]},
        )
        second = self.register(version=other)
        self.assertNotEqual(second.pk, first.pk)
        self.assertNotEqual(second.file.name, first.file.name)
        self.assertEqual(ModelArtifact.objects.count(), 2)
        self.assertEqual(len([path for path in self.root.rglob("*") if path.is_file()]), 2)

    def test_devices_with_identical_names_have_separate_directories(self):
        first = self.register()
        other = ModelVersion.objects.create(
            algorithm=self.version.algorithm, version=1,
            device_type=DeviceType.objects.create(name="device1"),
            architecture_params={}, input_spec={"features": ["signal1"]},
        )
        second = self.register(version=other, content=b"another device checkpoint")
        self.assertNotEqual(Path(first.file.name).parent.parent.parent, Path(second.file.name).parent.parent.parent)
        with first.file.open("rb") as stored:
            self.assertEqual(stored.read(), self.content)
        with second.file.open("rb") as stored:
            self.assertEqual(stored.read(), b"another device checkpoint")

    def test_registered_weights_cannot_be_replaced_with_different_bytes(self):
        artifact = self.register()
        with self.assertRaises(ValidationError):
            self.register(content=b"different checkpoint")
        with self.assertRaises(ValidationError):
            self.register(content=b"x" * len(self.content))
        self.version.refresh_from_db()
        self.assertEqual(self.version.weights, artifact)
        self.assertEqual(ModelArtifact.objects.count(), 1)
        with artifact.file.open("rb") as stored:
            self.assertEqual(stored.read(), self.content)

    def test_empty_file_and_unknown_version_do_not_create_artifacts(self):
        with self.assertRaises(ValidationError):
            self.register(content=b"")
        with self.assertRaises(ModelVersion.DoesNotExist):
            register_weights(uuid4(), ContentFile(self.content))
        self.assertFalse(ModelArtifact.objects.exists())
        self.assertFalse(list(self.root.rglob("*.bin")))

    def test_storage_failure_rolls_back_the_record_and_version_link(self):
        storage = ModelArtifact._meta.get_field("file").storage
        with patch.object(storage, "save", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.register()
        self.version.refresh_from_db()
        self.assertIsNone(self.version.weights_id)
        self.assertFalse(ModelArtifact.objects.exists())

    def test_existing_file_is_compared_and_missing_storage_is_not_recreated(self):
        artifact = self.register()
        path = Path(artifact.file.path)
        path.write_bytes(b"corrupted")
        with self.assertRaises(ValidationError):
            self.register()
        self.assertEqual(path.read_bytes(), b"corrupted")
        path.unlink()
        with self.assertRaisesMessage(ValidationError, "unavailable"):
            self.register()
        self.assertFalse(path.exists())
        self.version.refresh_from_db()
        self.assertEqual(self.version.weights_id, artifact.pk)

    def test_comparison_checks_the_entire_file_and_rejects_trailing_bytes(self):
        content = b"a" * (128 * 1024 + 3)
        artifact = self.register(content=content)
        self.assertEqual(self.register(content=content).pk, artifact.pk)
        with self.assertRaises(ValidationError):
            self.register(content=content[:-1] + b"b")
        path = Path(artifact.file.path)
        path.write_bytes(content + b"extra")
        with self.assertRaises(ValidationError):
            self.register(content=content)

    def test_file_left_after_a_failed_transaction_is_reused_on_retry(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.register()
                raise RuntimeError("transaction failed")
        self.assertFalse(ModelArtifact.objects.exists())
        self.version.refresh_from_db()
        self.assertIsNone(self.version.weights_id)
        files = list(self.root.rglob("*.bin"))
        self.assertEqual(len(files), 1)
        artifact = self.register()
        self.assertEqual(Path(artifact.file.path), files[0])
        self.assertEqual(ModelArtifact.objects.count(), 1)

    def test_referenced_artifact_is_protected_from_deletion(self):
        artifact = self.register()
        with self.assertRaises(ProtectedError):
            artifact.delete()

    def test_database_validates_size_and_unique_storage_path(self):
        artifact = self.register()
        for fields in [
            {"file": "model_weights/other.bin", "size_bytes": 0},
            {"file": artifact.file.name, "size_bytes": artifact.size_bytes},
            {"file": " ", "size_bytes": 1},
        ]:
            with self.subTest(fields=fields):
                invalid = ModelArtifact(**fields)
                with self.assertRaises(ValidationError):
                    invalid.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    invalid.save()

    def test_management_command_registers_without_loading_the_checkpoint(self):
        source = self.root / "checkpoint"
        source.write_bytes(self.content)
        output = StringIO()
        call_command("register_model_weights", str(self.version.pk), str(source), stdout=output)
        self.assertIn(
            f"model_weights/{self.version.device_type_id}/lstm_ae/v1/weights.bin", output.getvalue(),
        )
        self.assertNotIn("SHA256", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("register_model_weights", str(self.version.pk), str(self.root / "missing"))
