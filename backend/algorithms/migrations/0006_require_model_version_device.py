import django.db.models.deletion
from django.db import migrations, models


def assign_unambiguous_device(apps, schema_editor):
    alias = schema_editor.connection.alias
    versions = apps.get_model("algorithms", "ModelVersion").objects.using(alias).filter(device_type__isnull=True)
    if not versions.exists():
        return
    devices = list(apps.get_model("devices", "DeviceType").objects.using(alias).values_list("pk", flat=True)[:2])
    if len(devices) != 1:
        raise RuntimeError(
            "Existing model versions need an explicit device type. "
            "Migrate algorithms to 0005, assign device_type_id to each model version, then migrate again."
        )
    versions.update(device_type_id=devices[0])


class Migration(migrations.Migration):
    dependencies = [
        ("algorithms", "0005_model_version_device"),
    ]

    operations = [
        migrations.RunPython(assign_unambiguous_device, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="modelversion", name="device_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="model_versions", to="devices.devicetype",
            ),
        ),
    ]
