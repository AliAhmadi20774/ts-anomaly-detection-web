import re
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


def register_weights(model_version_id, source: File, *, device_folder: str | None = None) -> ModelArtifact:
    """Copy weights without hashing, deserializing or executing the checkpoint.

    Device folders organize storage without a device relationship in the database.
    An existing file is compared directly on retries; weights cannot be replaced.
    """
    if device_folder is not None and (
        not isinstance(device_folder, str) or re.fullmatch(r"[\w-]{1,64}", device_folder) is None
    ):
        raise ValidationError("Device folder must contain 1-64 letters, digits, underscores or hyphens.")
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
            destination = (
                f"{device_folder}/{version.algorithm.key}/v{version.version}/weights.bin"
                if device_folder is not None else None
            )
            if version.weights_id:
                artifact = version.weights
                if destination is not None and artifact.file.name != destination:
                    raise ValidationError("This version already has a file in another location; its folder cannot be replaced.")
                if artifact.size_bytes != size:
                    raise ValidationError("This version already has different weights. Register a new model version.")
                _ensure_file(artifact, snapshot, allow_create=False)
            else:
                if destination is None:
                    raise ValidationError("Specify a device folder when registering a new weights file.")
                artifact = ModelArtifact(
                    file=destination,
                    size_bytes=size,
                )
                artifact.full_clean()
                _ensure_file(artifact, snapshot, allow_create=True)
                artifact.full_clean()
                artifact.save()
                version.weights = artifact
                version.save(update_fields=["weights"])
            return artifact
