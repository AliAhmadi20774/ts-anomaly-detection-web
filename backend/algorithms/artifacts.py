from hashlib import sha256
from tempfile import SpooledTemporaryFile

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction

from algorithms.models import ModelArtifact, ModelVersion


def _ensure_file(artifact, snapshot):
    storage = artifact.file.storage
    if storage.exists(artifact.file.name):
        digest = sha256()
        size = 0
        with storage.open(artifact.file.name, "rb") as stored:
            for chunk in stored.chunks():
                digest.update(chunk)
                size += len(chunk)
        if size != artifact.size_bytes or digest.hexdigest() != artifact.sha256:
            raise ValidationError("Stored model file does not match its registered size or SHA256.")
        return
    snapshot.seek(0)
    artifact.file.name = storage.save(artifact.file.name, File(snapshot))
    artifact.full_clean()
    artifact.save(update_fields=["file"])


def register_weights(model_version_id, source: File) -> ModelArtifact:
    """Copy and hash weights without deserializing or executing the checkpoint.

    The source is snapshotted once so the digest describes the bytes we store.
    A file left by a failed database commit can be verified and reused on retry.
    """
    with SpooledTemporaryFile(max_size=16 * 1024 * 1024) as snapshot:
        digest = sha256()
        size = 0
        for chunk in source.chunks():
            snapshot.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        if size == 0:
            raise ValidationError("The model file is empty.")
        fingerprint = digest.hexdigest()

        with transaction.atomic():
            version = ModelVersion.objects.select_for_update().get(pk=model_version_id)
            version.full_clean()
            if version.weights_id:
                artifact = version.weights
                if artifact.sha256 != fingerprint or artifact.size_bytes != size:
                    raise ValidationError("This version already has different weights. Register a new model version.")
            else:
                artifact, _ = ModelArtifact.objects.get_or_create(
                    sha256=fingerprint,
                    defaults={
                        "file": f"model_weights/{fingerprint[:2]}/{fingerprint}.bin",
                        "size_bytes": size,
                    },
                )
                if artifact.size_bytes != size:
                    raise ValidationError("Registered model file size does not match its SHA256 record.")
            artifact.full_clean()
            _ensure_file(artifact, snapshot)
            if not version.weights_id:
                version.weights = artifact
                version.save(update_fields=["weights"])
            return artifact
