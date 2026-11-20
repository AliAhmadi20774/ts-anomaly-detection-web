import uuid

import django.core.validators
import django.db.models.deletion
import django.db.models.functions.text
import django.db.models.lookups
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0006_definition_names_unique_per_parent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MeasurementBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("recorded_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="measurement_batches", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "measurement_batches", "ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="DeviceRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("serial_number", models.CharField(
                    max_length=128,
                    validators=[django.core.validators.RegexValidator(r"\S", "Enter a device serial number.")],
                )),
                ("batch", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="devices", to="devices.measurementbatch",
                )),
                ("device_type", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="device_runs", to="devices.devicetype",
                )),
            ],
            options={
                "db_table": "device_runs",
                "ordering": ["serial_number", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=django.db.models.lookups.GreaterThan(
                            django.db.models.functions.text.Length(
                                django.db.models.functions.text.Trim("serial_number")
                            ), 0,
                        ),
                        name="device_runs_serial_not_blank",
                    ),
                    models.UniqueConstraint(
                        fields=("batch", "device_type", "serial_number"),
                        name="device_runs_batch_type_serial_unique",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="testrun",
            name="device_run",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="test_runs", to="devices.devicerun",
            ),
        ),
    ]
