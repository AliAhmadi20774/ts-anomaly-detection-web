import uuid

import django.core.validators
from django.db import migrations, models


def seed_lstm_ae(apps, schema_editor):
    Algorithm = apps.get_model("algorithms", "Algorithm")
    Algorithm.objects.using(schema_editor.connection.alias).get_or_create(
        key="lstm_ae", defaults={"name": "LSTM Autoencoder"},
    )


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Algorithm",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=64, unique=True, validators=[
                    django.core.validators.RegexValidator(
                        "\\A[a-z][a-z0-9_]*\\Z",
                        "Use lowercase letters, digits and underscores, starting with a letter.",
                    ),
                ])),
                ("name", models.CharField(max_length=160, validators=[
                    django.core.validators.RegexValidator("\\S", "Name must contain a non-whitespace character."),
                ])),
            ],
            options={
                "db_table": "algorithms",
                "ordering": ["name", "id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(key__regex="\\A[a-z][a-z0-9_]*\\Z"), name="algorithms_key_format"),
                    models.CheckConstraint(condition=models.Q(name__regex="\\S"), name="algorithms_name_not_blank"),
                ],
            },
        ),
        migrations.RunPython(seed_lstm_ae, migrations.RunPython.noop),
    ]
