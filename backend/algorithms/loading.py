"""Load a registered model using its metadata and private Django storage."""

from tempfile import SpooledTemporaryFile

from django.core.exceptions import ValidationError

from algorithms.models import ModelVersion
from algorithms.runtimes.lstm_ae import LSTMAutoencoder, load_lstm_ae


def load_model_version(model_version_id) -> LSTMAutoencoder:
    """Read and validate a registered LSTM-AE version without changing storage.

    Files are opened through Django storage rather than an absolute local path,
    allowing the existing model mount or another configured storage backend.
    A seekable temporary snapshot is checked against the registered byte count
    before deserialization. Size is a consistency check, not a content hash.

    Unconfigured preprocessing does not block this weights-only check. It does
    not make that version ready for inference. Missing versions raise
    ModelVersion.DoesNotExist; invalid metadata or weights raise ValidationError.
    """
    version = ModelVersion.objects.select_related("algorithm", "weights").get(pk=model_version_id)
    version.full_clean()
    if version.algorithm.key != "lstm_ae":
        raise ValidationError("Model loading currently supports only the lstm_ae algorithm.")
    if version.weights_id is None:
        raise ValidationError("This model version has no registered weights.")
    artifact = version.weights
    with SpooledTemporaryFile(max_size=16 * 1024 * 1024) as snapshot:
        try:
            with artifact.file.open("rb") as source:
                size = 0
                while chunk := source.read(64 * 1024):
                    size += len(chunk)
                    if size > artifact.size_bytes:
                        raise ValidationError("Weights file size differs from its registered size.")
                    snapshot.write(chunk)
        except OSError as error:
            raise ValidationError("Registered weights are unavailable. Check storage or restore the file.") from error
        if size != artifact.size_bytes:
            raise ValidationError("Weights file size differs from its registered size.")
        snapshot.seek(0)
        try:
            return load_lstm_ae(snapshot, architecture_params=version.architecture_params, input_spec=version.input_spec)
        except ValueError as error:
            raise ValidationError(str(error)) from error
