from django.db import migrations, models


def rebase_paths(apps, schema_editor):
    artifacts = apps.get_model("algorithms", "ModelArtifact").objects.using(schema_editor.connection.alias)
    prefix = "model_weights/"
    for artifact in artifacts.filter(file__startswith=prefix).order_by("file").iterator():
        relative_path = artifact.file.name[len(prefix):]
        if not relative_path or artifacts.exclude(pk=artifact.pk).filter(file=relative_path).exists():
            raise RuntimeError("Model file paths conflict when switching to the models root; no files were moved.")
        artifacts.filter(pk=artifact.pk).update(file=relative_path)


def restore_paths(apps, schema_editor):
    artifacts = apps.get_model("algorithms", "ModelArtifact").objects.using(schema_editor.connection.alias)
    for artifact in artifacts.all().iterator():
        artifacts.filter(pk=artifact.pk).update(file=f"model_weights/{artifact.file.name}")


class Migration(migrations.Migration):
    dependencies = [
        ("algorithms", "0007_device_folders_only"),
    ]

    operations = [
        migrations.RunPython(rebase_paths, restore_paths),
        migrations.AlterField(
            model_name="modelartifact", name="file", field=models.FileField(max_length=255, unique=True),
        ),
    ]
