from django.db import migrations


def move_existing_runs(apps, schema_editor):
    TestRun = apps.get_model("devices", "TestRun")
    MeasurementBatch = apps.get_model("devices", "MeasurementBatch")
    DeviceRun = apps.get_model("devices", "DeviceRun")
    alias = schema_editor.connection.alias

    # The old schema did not record upload-request identity. Imported runs can
    # only be grouped reliably by source file; manual runs each get one batch.
    file_hashes = list(
        TestRun.objects.using(alias)
        .exclude(source_file_sha256="")
        .order_by()
        .values_list("source_file_sha256", flat=True)
        .distinct()
    )
    for digest in file_hashes:
        runs = list(
            TestRun.objects.using(alias)
            .filter(source_file_sha256=digest)
            .order_by("created_at", "id")
        )
        batch = MeasurementBatch.objects.using(alias).create(
            created_at=runs[0].created_at, recorded_by_id=runs[0].recorded_by_id,
        )
        devices = {}
        for run in runs:
            key = (run.device_type_id, run.device_serial_number)
            if key not in devices:
                devices[key] = DeviceRun.objects.using(alias).create(
                    batch_id=batch.pk,
                    device_type_id=run.device_type_id,
                    serial_number=run.device_serial_number,
                )
            TestRun.objects.using(alias).filter(pk=run.pk).update(device_run_id=devices[key].pk)

    for run in TestRun.objects.using(alias).filter(source_file_sha256="").iterator():
        batch = MeasurementBatch.objects.using(alias).create(
            created_at=run.created_at, recorded_by_id=run.recorded_by_id,
        )
        device = DeviceRun.objects.using(alias).create(
            batch_id=batch.pk,
            device_type_id=run.device_type_id,
            serial_number=run.device_serial_number,
        )
        TestRun.objects.using(alias).filter(pk=run.pk).update(device_run_id=device.pk)


class Migration(migrations.Migration):
    dependencies = [("devices", "0007_measurement_batches")]

    operations = [migrations.RunPython(move_existing_runs, migrations.RunPython.noop)]
