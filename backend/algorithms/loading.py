"""Load a registered model using its metadata and private Django storage."""

from tempfile import SpooledTemporaryFile
from typing import BinaryIO

from django.core.exceptions import ValidationError

from algorithms.models import ModelArtifact, ModelVersion
from algorithms.runtimes.contracts import ModelRuntime
from algorithms.runtimes.registry import get_model_loader


def load_model_version(model_version_id) -> ModelRuntime:
    """Load a stored version with the function selected by its algorithm key.

    Unconfigured preprocessing does not block this weights-only check. It does
    not make that version ready for inference. Missing versions raise
    ModelVersion.DoesNotExist; invalid metadata or weights raise ValidationError.
    """
    version = ModelVersion.objects.select_related("algorithm", "weights").get(pk=model_version_id)
    version.full_clean()

    try:
        loader = get_model_loader(version.algorithm.key)
    except ValueError as error:
        raise ValidationError(str(error)) from error

    if version.weights_id is None:
        raise ValidationError("This model version has no registered weights.")
    expected_features = tuple(version.input_spec["features"])

    # Every algorithm receives the same seekable stream and metadata arguments.
    with SpooledTemporaryFile(max_size=16 * 1024 * 1024) as snapshot:
        _copy_weights_to_snapshot(version.weights, snapshot)
        try:
            runtime = loader(
                snapshot,
                architecture_params=version.architecture_params,
                input_spec=version.input_spec,
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error

    _validate_runtime(runtime, algorithm_key=version.algorithm.key, features=expected_features)
    return runtime


def _copy_weights_to_snapshot(artifact: ModelArtifact, snapshot: BinaryIO) -> None:
    """Copy storage bytes and verify their registered size before deserialization.

    Use the storage API so local files and other configured storage backends
    follow the same path. Byte count checks consistency, not content identity.
    """
    size = 0
    try:
        with artifact.file.open("rb") as source:
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


def _validate_runtime(runtime: object, *, algorithm_key: str, features: tuple[str, ...]) -> None:
    """Reject a loader result for the wrong algorithm or input signal order."""
    if not isinstance(runtime, ModelRuntime):
        raise ValidationError("The registered loader must return a ModelRuntime.")
    if runtime.algorithm_key != algorithm_key:
        raise ValidationError("Loaded runtime algorithm does not match the model version.")
    if runtime.features != features:
        raise ValidationError("Loaded runtime features do not match input_spec.features in order.")
