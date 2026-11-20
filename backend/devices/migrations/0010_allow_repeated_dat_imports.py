from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("devices", "0009_finalize_measurement_batches")]

    operations = [
        migrations.RemoveConstraint(
            model_name="testrun",
            name="test_runs_source_position_unique",
        ),
    ]
