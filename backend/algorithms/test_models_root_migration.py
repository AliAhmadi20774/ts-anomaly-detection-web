from pathlib import Path
from tempfile import TemporaryDirectory

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from algorithms.models import ModelArtifact, ModelVersion


class ModelsRootMigrationTests(TransactionTestCase):
    previous = ("algorithms", "0007_device_folders_only")
    target = ("algorithms", "0008_models_root")

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.previous])
        self.apps = executor.loader.project_state([self.previous]).apps

    def tearDown(self):
        ModelVersion.objects.all().delete()
        ModelArtifact.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_rebased_record_resolves_to_existing_local_file_without_moving_it(self):
        relative = "device1/lstm_ae/v1/weights.bin"
        artifact = self.apps.get_model("algorithms", "ModelArtifact").objects.create(
            file=f"model_weights/{relative}", size_bytes=5,
        )
        algorithm, _ = self.apps.get_model("algorithms", "Algorithm").objects.get_or_create(
            key="lstm_ae", defaults={"name": "LSTM Autoencoder"},
        )
        version = self.apps.get_model("algorithms", "ModelVersion").objects.create(
            algorithm=algorithm, version=1, weights=artifact,
            architecture_params={}, input_spec={"features": ["signal1"]},
        )
        with TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
            path = Path(root) / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"model")
            MigrationExecutor(connection).migrate([self.target])
            stored = ModelArtifact.objects.get(pk=artifact.pk)
            self.assertEqual(stored.file.name, relative)
            self.assertEqual(ModelVersion.objects.get(pk=version.pk).weights_id, artifact.pk)
            with stored.file.open("rb") as weights:
                self.assertEqual(weights.read(), b"model")
            self.assertEqual(list(Path(root).rglob("*.bin")), [path])

    def test_conflicting_paths_fail_without_replacing_records(self):
        model = self.apps.get_model("algorithms", "ModelArtifact")
        old = model.objects.create(file="model_weights/device1/weights.bin", size_bytes=5)
        other = model.objects.create(file="device1/weights.bin", size_bytes=7)
        with self.assertRaisesMessage(RuntimeError, "paths conflict"):
            MigrationExecutor(connection).migrate([self.target])
        old.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(old.file.name, "model_weights/device1/weights.bin")
        self.assertEqual(other.file.name, "device1/weights.bin")
