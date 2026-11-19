import uuid

import django.core.validators
from django.db import migrations, models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThan


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DeviceType",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "name",
                    models.TextField(
                        validators=[
                            django.core.validators.RegexValidator(
                                r"\S", "Name must contain a non-whitespace character."
                            ),
                        ],
                    ),
                ),
            ],
            options={
                "db_table": "device_types",
                "ordering": ["name", "id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=GreaterThan(Length(Trim("name")), 0),
                        name="device_types_name_check",
                    ),
                ],
            },
        ),
    ]
