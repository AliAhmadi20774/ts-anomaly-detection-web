import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("algorithms", "0004_remove_model_weights_hash"),
        ("devices", "0010_allow_repeated_dat_imports"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelversion",
            name="device_type",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="model_versions", to="devices.devicetype",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="modelversion", name="model_versions_algorithm_version_unique",
        ),
        migrations.AddConstraint(
            model_name="modelversion",
            constraint=models.UniqueConstraint(
                fields=("device_type", "algorithm", "version"),
                name="model_versions_device_algorithm_version_unique",
            ),
        ),
        migrations.AlterModelOptions(
            name="modelversion", options={"ordering": ["device_type", "algorithm", "version"]},
        ),
    ]
