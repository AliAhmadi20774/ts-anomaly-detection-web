from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from algorithms.models import ModelVersion


class StorageOnlyMigrationTests(TransactionTestCase):
    previous = ("algorithms", "0006_require_model_version_device")
    target = ("algorithms", "0007_device_folders_only")

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.previous])
        self.apps = executor.loader.project_state([self.previous]).apps
        self.algorithm, _ = self.apps.get_model("algorithms", "Algorithm").objects.get_or_create(
            key="lstm_ae", defaults={"name": "LSTM Autoencoder"},
        )

    def tearDown(self):
        # Both schemas have the same non-device fields; remove test versions so
        # the latest schema can be restored even after a deliberate conflict.
        ModelVersion.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def create_version(self, name, **fields):
        device = self.apps.get_model("devices", "DeviceType").objects.create(name=name)
        return self.apps.get_model("algorithms", "ModelVersion").objects.create(
            algorithm=self.algorithm, device_type=device, version=1,
            architecture_params={"hidden_size": 300}, input_spec={"features": ["signal1"]}, **fields,
        )

    def test_removing_device_relationship_preserves_model_and_file_metadata(self):
        artifact = self.apps.get_model("algorithms", "ModelArtifact").objects.create(
            file="model_weights/device1/lstm_ae/v1/weights.bin", size_bytes=123,
        )
        version = self.create_version("device1", weights=artifact)
        MigrationExecutor(connection).migrate([self.target])
        stored = ModelVersion.objects.get(pk=version.pk)
        self.assertEqual(stored.weights_id, artifact.pk)
        self.assertEqual(stored.weights.file.name, artifact.file.name)
        self.assertEqual(stored.architecture_params, {"hidden_size": 300})
        self.assertEqual(stored.input_spec, {"features": ["signal1"]})
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(cursor, "model_versions")
        self.assertNotIn("device_type_id", [column.name for column in columns])

    def test_conflicting_versions_abort_without_losing_device_information(self):
        first = self.create_version("device1")
        second = self.create_version("device2")
        with self.assertRaises(IntegrityError):
            MigrationExecutor(connection).migrate([self.target])
        for version in [first, second]:
            version.refresh_from_db()
            self.assertIsNotNone(version.device_type_id)
