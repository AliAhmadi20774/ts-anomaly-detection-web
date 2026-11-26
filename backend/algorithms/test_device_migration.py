from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ModelDeviceMigrationTests(TransactionTestCase):
    previous = ("algorithms", "0005_model_version_device")
    target = ("algorithms", "0006_require_model_version_device")

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.previous])
        self.apps = executor.loader.project_state([self.previous]).apps

    def tearDown(self):
        # Restore the current schema even when the migration deliberately fails.
        self.apps.get_model("algorithms", "ModelVersion").objects.filter(device_type__isnull=True).delete()
        MigrationExecutor(connection).migrate([self.target])
        super().tearDown()

    def create_version(self):
        algorithm, _ = self.apps.get_model("algorithms", "Algorithm").objects.get_or_create(
            key="lstm_ae", defaults={"name": "LSTM Autoencoder"},
        )
        return self.apps.get_model("algorithms", "ModelVersion").objects.create(
            algorithm=algorithm, version=1, architecture_params={}, input_spec={"features": ["signal1"]},
        )

    def test_single_device_is_assigned_to_existing_version(self):
        device = self.apps.get_model("devices", "DeviceType").objects.create(name="device1")
        version = self.create_version()
        MigrationExecutor(connection).migrate([self.target])
        version.refresh_from_db()
        self.assertEqual(version.device_type_id, device.pk)

    def test_ambiguous_device_requires_explicit_assignment(self):
        device_model = self.apps.get_model("devices", "DeviceType")
        device_model.objects.create(name="device1")
        chosen = device_model.objects.create(name="device2")
        version = self.create_version()
        with self.assertRaisesMessage(RuntimeError, "explicit device type"):
            MigrationExecutor(connection).migrate([self.target])
        version.refresh_from_db()
        self.assertIsNone(version.device_type_id)
        version.device_type_id = chosen.pk
        version.save(update_fields=["device_type"])
        MigrationExecutor(connection).migrate([self.target])
        version.refresh_from_db()
        self.assertEqual(version.device_type_id, chosen.pk)
