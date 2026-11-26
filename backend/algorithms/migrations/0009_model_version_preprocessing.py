import algorithms.validators
import django.db.models.lookups
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("algorithms", "0008_models_root"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelversion", name="preprocessing",
            field=models.JSONField(
                blank=True, default=None, null=True, validators=[algorithms.validators.PreprocessingValidator()],
            ),
        ),
        migrations.AddConstraint(
            model_name="modelversion",
            constraint=models.CheckConstraint(
                condition=models.Q(preprocessing__isnull=True) | django.db.models.lookups.Exact(
                    models.Func("preprocessing", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("object"),
                ),
                name="model_versions_preprocessing_object",
            ),
        ),
    ]
