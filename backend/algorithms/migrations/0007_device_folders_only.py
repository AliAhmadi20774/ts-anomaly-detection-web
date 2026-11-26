from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("algorithms", "0006_require_model_version_device"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="modelversion", name="model_versions_device_algorithm_version_unique",
        ),
        # Restore uniqueness before dropping device information. Conflicting
        # versions abort this atomic migration instead of losing records.
        migrations.AddConstraint(
            model_name="modelversion",
            constraint=models.UniqueConstraint(
                fields=("algorithm", "version"), name="model_versions_algorithm_version_unique",
            ),
        ),
        migrations.RemoveField(model_name="modelversion", name="device_type"),
        migrations.AlterModelOptions(
            name="modelversion", options={"ordering": ["algorithm", "version"]},
        ),
    ]
