from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("devices", "0005_dat_signal_traces")]

    operations = [
        migrations.AddConstraint(
            model_name="testdefinition",
            constraint=models.UniqueConstraint(
                fields=("device_type", "name"),
                name="test_definitions_device_type_name_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="signaldefinition",
            constraint=models.UniqueConstraint(
                fields=("test", "name"),
                name="signal_definitions_test_name_unique",
            ),
        ),
    ]
