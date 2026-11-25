from tempfile import SpooledTemporaryFile

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction

from algorithms.models import ModelArtifact, ModelVersion


def _ensure_file(artifact, snapshot, *, allow_create):
    storage = artifact.file.storage
    snapshot.seek(0)
    if storage.exists(artifact.file.name):
        with storage.open(artifact.file.name, "rb") as stored:
            while chunk := snapshot.read(64 * 1024):
                if stored.read(len(chunk)) != chunk:
                    raise ValidationError("This version already has different weights. Register a new model version.")
            if stored.read(1):
                raise ValidationError("This version already has different weights. Register a new model version.")
        return
    if not allow_create:
        raise ValidationError("Registered model file is unavailable. Check the storage mount or restore its backup.")
    snapshot.seek(0)
    artifact.file.name = storage.save(artifact.file.name, File(snapshot))


def register_weights(model_version_id, source: File) -> ModelArtifact:
    """Copy weights without hashing, deserializing or executing the checkpoint.

    Each model version has its own storage path. An existing file is compared
    directly with the source on retries; registered weights cannot be replaced.
    """
    with SpooledTemporaryFile(max_size=16 * 1024 * 1024) as snapshot:
        size = 0
        for chunk in source.chunks():
            snapshot.write(chunk)
            size += len(chunk)
        if size == 0:
            raise ValidationError("The model file is empty.")
        with transaction.atomic():
            version = ModelVersion.objects.select_for_update().get(pk=model_version_id)
            version.full_clean()
            if version.weights_id:
                artifact = version.weights
                if artifact.size_bytes != size:
                    raise ValidationError("This version already has different weights. Register a new model version.")
                _ensure_file(artifact, snapshot, allow_create=False)
            else:
                artifact = ModelArtifact(
                    file=f"model_weights/{version.pk}/weights.bin",
                    size_bytes=size,
                )
                artifact.full_clean()
                _ensure_file(artifact, snapshot, allow_create=True)
                artifact.full_clean()
                artifact.save()
                version.weights = artifact
                version.save(update_fields=["weights"])
            return artifact
