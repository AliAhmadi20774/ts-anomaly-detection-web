from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("algorithms", "0003_model_weights"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="modelartifact",
            name="model_artifacts_hash_format",
        ),
        migrations.RemoveField(
            model_name="modelartifact",
            name="sha256",
        ),
    ]
