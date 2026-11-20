import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("devices", "0008_backfill_measurement_batches")]

    operations = [
        migrations.AlterField(
            model_name="testrun",
            name="device_run",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="test_runs", to="devices.devicerun",
            ),
        ),
        migrations.RemoveField(model_name="testrun", name="created_at"),
        migrations.RemoveField(model_name="testrun", name="notes"),
    ]
